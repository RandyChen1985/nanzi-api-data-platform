import logging
import json
import re
import asyncio
import inspect
from typing import Any, Optional, Dict, List
from datetime import datetime
from fastapi import BackgroundTasks

from app.core.database import get_db_connection
from app.services.datasource_service import DataSourceService
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)

PROFILE_CANCEL_MESSAGE = "用户主动取消摸排"
_PROFILE_INIT_BATCH_SIZE = 500
_ZOMBIE_TABLE_STALE_MINUTES = 10
_TASK_STATUS_DONE = 2
_TASK_STATUS_RUNNING = 1
_HEAVY_COLUMN_TYPE_PATTERN = re.compile(
    r"\b(BLOB|CLOB|NCLOB|LONG RAW|LONG|BYTEA|IMAGE|VARBINARY|BINARY|RAW)\b",
    re.IGNORECASE,
)
_SAMPLE_COLUMN_LIMIT = 24


class DbProfileService:
    """外部数据源元数据智能摸排与分析服务"""

    @staticmethod
    def is_cancelled_task(task: Optional[Dict[str, Any]]) -> bool:
        if not task:
            return False
        return (
            task.get("status") == 3
            and (task.get("error_message") or "").startswith(PROFILE_CANCEL_MESSAGE)
        )

    @staticmethod
    async def trigger_profiling_task(
        source_id: int,
        background_tasks: BackgroundTasks,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        触发该数据源配置下所有表和视图的智能分析摸排后台任务（一个数据源只允许一个进行中的任务）
        force=True 时重置全部表为待摸排并从头全量重跑（含已成功表，会重新消耗 LLM Token）
        """
        # 1. 检查数据源配置是否存在
        datasource = await DataSourceService.get_datasource(source_id)
        if not datasource:
            raise ValueError("数据源配置不存在")

        # 2. 检查是否有进行中的任务 (status = 1)
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT id, status FROM db_profile_tasks WHERE connection_id = %s",
                    (source_id,)
                )
                existing_task = await cursor.fetchone()

                await DbProfileService._reconcile_profiling_task_status_with_cursor(cursor, source_id)
                if existing_task and existing_task[1] == _TASK_STATUS_RUNNING:
                    await cursor.execute(
                        "SELECT status FROM db_profile_tasks WHERE connection_id = %s",
                        (source_id,),
                    )
                    refreshed = await cursor.fetchone()
                    if refreshed and refreshed[0] == _TASK_STATUS_RUNNING:
                        raise ValueError("当前数据源分析摸排任务正在执行中，请勿重复点击")

                # 3. 实例化适配器并查询数据库下所有的表/视图
                from app.services.data_adapter.factory import get_adapter
                adapter = await get_adapter(datasource.source_name)
                tables_info = await adapter.get_tables()
                total_count = len(tables_info)

                await cursor.execute(
                    """
                    SELECT COUNT(*) FROM db_table_profiles
                    WHERE connection_id = %s AND status = 2
                    """,
                    (source_id,)
                )
                done_count_row = await cursor.fetchone()
                done_count = 0 if force else int(done_count_row[0] if done_count_row else 0)

                # 4. Upsert 主任务状态（续跑时保留已完成进度；全量重跑从 0 开始）
                if existing_task:
                    await cursor.execute(
                        """
                        UPDATE db_profile_tasks
                        SET status = 1, total_tables = %s, processed_tables = %s,
                            current_table = NULL, error_message = NULL, updated_at = NOW()
                        WHERE connection_id = %s
                        """,
                        (total_count, done_count, source_id)
                    )
                else:
                    await cursor.execute(
                        """
                        INSERT INTO db_profile_tasks (connection_id, status, total_tables, processed_tables)
                        VALUES (%s, 1, %s, %s)
                        """,
                        (source_id, total_count, done_count)
                    )

                # 5. 准备并初始化子表记录 (db_table_profiles)
                await cursor.execute(
                    "SELECT id, table_name FROM db_table_profiles WHERE connection_id = %s",
                    (source_id,)
                )
                sub_rows = await cursor.fetchall()
                existing_profiles = {row[1]: row[0] for row in sub_rows}
                await DbProfileService._bulk_init_table_profiles(
                    cursor, source_id, tables_info, existing_profiles, force=force
                )
                
                await conn.commit()

        # 6. 加入 FastAPI 后台任务
        background_tasks.add_task(DbProfileService.run_profiling_loop, source_id)
        
        # 重新查询当前任务对象返回
        return await DbProfileService.get_task_status(source_id)

    @staticmethod
    async def cancel_profiling_task(source_id: int) -> Dict[str, Any]:
        """请求中断进行中的摸排任务（当前表处理完成后停止）"""
        task = await DbProfileService.get_task_status(source_id)
        if not task or task.get("status") != 1:
            raise ValueError("当前没有进行中的摸排任务")

        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE db_profile_tasks
                    SET status = 3, error_message = %s, current_table = NULL, updated_at = NOW()
                    WHERE connection_id = %s AND status = 1
                    """,
                    (PROFILE_CANCEL_MESSAGE, source_id)
                )
                if cursor.rowcount == 0:
                    raise ValueError("摸排任务状态已变更，请刷新后重试")

                await cursor.execute(
                    """
                    UPDATE db_table_profiles
                    SET status = 0, updated_at = NOW()
                    WHERE connection_id = %s AND status = 1
                    """,
                    (source_id,)
                )
                await conn.commit()

        logger.info(f"[DbProfiling] Profiling task cancelled for source_id: {source_id}")
        updated = await DbProfileService.get_task_status(source_id)
        return updated or task

    @staticmethod
    async def _should_stop_profiling(source_id: int) -> bool:
        task = await DbProfileService.get_task_status(source_id)
        return not task or task.get("status") != 1

    @staticmethod
    async def _reconcile_profiling_task_status_with_cursor(cursor, source_id: int) -> bool:
        """基于子表状态校正主任务；重置长时间无心跳的僵尸表。返回是否有写库变更。"""
        await cursor.execute(
            """
            UPDATE db_table_profiles
            SET status = 0, updated_at = NOW()
            WHERE connection_id = %s AND status = 1
              AND updated_at < DATE_SUB(NOW(), INTERVAL %s MINUTE)
            """,
            (source_id, _ZOMBIE_TABLE_STALE_MINUTES),
        )
        changed = cursor.rowcount > 0

        await cursor.execute(
            "SELECT status, total_tables FROM db_profile_tasks WHERE connection_id = %s",
            (source_id,),
        )
        task_row = await cursor.fetchone()
        if not task_row or task_row[0] != _TASK_STATUS_RUNNING:
            return changed

        total_tables = int(task_row[1] or 0)
        await cursor.execute(
            """
            SELECT status, COUNT(*) AS cnt
            FROM db_table_profiles
            WHERE connection_id = %s
            GROUP BY status
            """,
            (source_id,),
        )
        counts = {row[0]: int(row[1]) for row in await cursor.fetchall()}
        pending = counts.get(0, 0)
        in_progress = counts.get(1, 0)
        success = counts.get(2, 0)
        failed = counts.get(3, 0)
        finished = success + failed

        if pending > 0 or in_progress > 0 or finished == 0:
            return changed

        processed_tables = total_tables if total_tables > 0 else finished
        await cursor.execute(
            """
            UPDATE db_profile_tasks
            SET status = %s, processed_tables = %s, current_table = NULL,
                error_message = NULL, updated_at = NOW()
            WHERE connection_id = %s AND status = %s
            """,
            (_TASK_STATUS_DONE, processed_tables, source_id, _TASK_STATUS_RUNNING),
        )
        if cursor.rowcount > 0:
            changed = True
            logger.info(
                "[DbProfiling] Reconciled main task for source_id=%s: success=%s failed=%s total=%s",
                source_id, success, failed, processed_tables,
            )
        return changed

    @staticmethod
    async def reconcile_profiling_task_status(source_id: int) -> bool:
        """对外暴露的状态校正入口（打开数据源页/轮询任务时调用）。"""
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                changed = await DbProfileService._reconcile_profiling_task_status_with_cursor(
                    cursor, source_id
                )
                if changed:
                    await conn.commit()
                return changed

    @staticmethod
    async def get_task_status(source_id: int, reconcile: bool = True) -> Optional[Dict[str, Any]]:
        """获取该数据源当前摸排任务进度与状态"""
        if reconcile:
            await DbProfileService.reconcile_profiling_task_status(source_id)

        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT COUNT(*) FROM db_table_profiles
                    WHERE connection_id = %s AND status = 2
                    """,
                    (source_id,),
                )
                completed_row = await cursor.fetchone()
                completed_profiles = int(completed_row[0]) if completed_row else 0

                await cursor.execute(
                    """
                    SELECT MAX(updated_at) FROM db_table_profiles
                    WHERE connection_id = %s AND status = 2
                    """,
                    (source_id,),
                )
                last_profiled_row = await cursor.fetchone()
                last_profiled_at = last_profiled_row[0] if last_profiled_row else None

                await cursor.execute(
                    """
                    SELECT id, connection_id, status, total_tables, processed_tables,
                           current_table, error_message, created_at, updated_at
                    FROM db_profile_tasks
                    WHERE connection_id = %s
                    """,
                    (source_id,)
                )
                row = await cursor.fetchone()
                if not row:
                    if completed_profiles <= 0:
                        return None
                    return {
                        "id": 0,
                        "connection_id": source_id,
                        "status": 0,
                        "total_tables": 0,
                        "processed_tables": completed_profiles,
                        "completed_profiles": completed_profiles,
                        "last_profiled_at": last_profiled_at,
                        "current_table": None,
                        "error_message": None,
                        "created_at": None,
                        "updated_at": None,
                    }
                return {
                    "id": row[0],
                    "connection_id": row[1],
                    "status": row[2],
                    "total_tables": row[3],
                    "processed_tables": row[4],
                    "completed_profiles": completed_profiles,
                    "last_profiled_at": last_profiled_at,
                    "current_table": row[5],
                    "error_message": row[6],
                    "created_at": row[7],
                    "updated_at": row[8]
                }

    @staticmethod
    def _parse_json_field(value: Any, default: Any):
        if value is None:
            return default
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return default
        return default

    @staticmethod
    async def _bulk_init_table_profiles(
        cursor,
        source_id: int,
        tables_info: List[Dict[str, str]],
        existing_profiles: Dict[str, int],
        force: bool = False,
    ) -> None:
        active_table_names = {t["name"] for t in tables_info}

        stale_ids = [p_id for t_name, p_id in existing_profiles.items() if t_name not in active_table_names]
        if stale_ids:
            placeholders = ",".join(["%s"] * len(stale_ids))
            await cursor.execute(
                f"DELETE FROM db_table_profiles WHERE id IN ({placeholders})",
                stale_ids,
            )
            for t_name in list(existing_profiles.keys()):
                if t_name not in active_table_names:
                    del existing_profiles[t_name]

        updates: List[tuple] = []
        inserts: List[tuple] = []
        for table in tables_info:
            t_name = table["name"]
            t_type = table.get("type", "table").lower()
            if t_name in existing_profiles:
                updates.append((t_type, source_id, t_name))
            else:
                inserts.append((source_id, t_name, t_type, 0))

        if updates:
            status_filter = "" if force else " AND status != 2"
            await cursor.executemany(
                f"""
                UPDATE db_table_profiles
                SET status = 0, error_message = NULL, table_type = %s, updated_at = NOW()
                WHERE connection_id = %s AND table_name = %s{status_filter}
                """,
                updates,
            )

        for offset in range(0, len(inserts), _PROFILE_INIT_BATCH_SIZE):
            chunk = inserts[offset: offset + _PROFILE_INIT_BATCH_SIZE]
            if chunk:
                await cursor.executemany(
                    """
                    INSERT INTO db_table_profiles (connection_id, table_name, table_type, status)
                    VALUES (%s, %s, %s, %s)
                    """,
                    chunk,
                )

    @staticmethod
    def _is_heavy_column_type(col_type: str) -> bool:
        return bool(_HEAVY_COLUMN_TYPE_PATTERN.search(col_type or ""))

    @staticmethod
    def _quote_identifier(db_type: str, name: str) -> str:
        quote = "`" if db_type in ("mysql", "clickhouse") else '"'
        return f"{quote}{name}{quote}"

    @classmethod
    async def _build_sample_query(cls, adapter, db_type: str, table_name: str) -> str:
        quote = "`" if db_type in ("mysql", "clickhouse") else '"'
        table_ref = (
            f"{quote}{table_name.upper()}{quote}"
            if db_type == "oracle"
            else f"{quote}{table_name}{quote}"
        )

        try:
            columns = await adapter.get_columns(table_name)
            safe_cols = [
                col["name"]
                for col in columns
                if col.get("name") and not cls._is_heavy_column_type(col.get("type", ""))
            ]
            if not safe_cols and columns:
                safe_cols = [columns[0]["name"]]
            if safe_cols:
                safe_cols = safe_cols[:_SAMPLE_COLUMN_LIMIT]
                col_sql = ", ".join(cls._quote_identifier(db_type, col) for col in safe_cols)
                select_expr = col_sql
            else:
                select_expr = "*"
        except Exception as exc:
            logger.debug(f"[DbProfiling] Fallback to SELECT * for {table_name}: {exc}")
            select_expr = "*"

        if db_type == "oracle":
            return f"SELECT {select_expr} FROM {table_ref} WHERE ROWNUM <= 3"
        if db_type in ("sqlserver", "mssql", "tsql"):
            return f"SELECT TOP 3 {select_expr} FROM {table_ref}"
        return f"SELECT {select_expr} FROM {table_ref} LIMIT 3"

    @staticmethod
    async def list_table_profiles(
        source_id: int,
        summary: bool = False,
        status: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """获取该数据源下已摸排/分析的表画像列表"""
        conditions = ["connection_id = %s"]
        params: List[Any] = [source_id]
        if status is not None:
            conditions.append("status = %s")
            params.append(status)

        where_clause = " AND ".join(conditions)
        if summary:
            sql = f"""
                SELECT id, connection_id, table_name, table_type,
                       ai_term, ai_description, ai_tags, status, error_message,
                       confidence_score, is_temporary, is_ignored, confidence_reason,
                       created_at, updated_at,
                       JSON_LENGTH(columns_profile) AS columns_count
                FROM db_table_profiles
                WHERE {where_clause}
                ORDER BY table_name ASC
            """
        else:
            sql = f"""
                SELECT id, connection_id, table_name, table_type, engine, ddl, sample_data,
                       ai_term, ai_description, ai_tags, columns_profile, status, error_message,
                       confidence_score, is_temporary, is_ignored, confidence_reason, created_at, updated_at
                FROM db_table_profiles
                WHERE {where_clause}
                ORDER BY table_name ASC
            """

        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql, tuple(params))
                rows = await cursor.fetchall()

        profiles = []
        for row in rows:
            if summary:
                ai_tags = DbProfileService._parse_json_field(row[6], [])
                profiles.append({
                    "id": row[0],
                    "connection_id": row[1],
                    "table_name": row[2],
                    "table_type": row[3],
                    "ai_term": row[4],
                    "ai_description": row[5],
                    "ai_tags": ai_tags or [],
                    "status": row[7],
                    "error_message": row[8],
                    "confidence_score": row[9],
                    "is_temporary": row[10],
                    "is_ignored": row[11],
                    "confidence_reason": row[12],
                    "created_at": row[13],
                    "updated_at": row[14],
                    "columns_count": int(row[15] or 0),
                })
            else:
                sample_data = DbProfileService._parse_json_field(row[6], row[6])
                ai_tags = DbProfileService._parse_json_field(row[9], [])
                columns_profile = DbProfileService._parse_json_field(row[10], [])
                profiles.append({
                    "id": row[0],
                    "connection_id": row[1],
                    "table_name": row[2],
                    "table_type": row[3],
                    "engine": row[4],
                    "ddl": row[5],
                    "sample_data": sample_data,
                    "ai_term": row[7],
                    "ai_description": row[8],
                    "ai_tags": ai_tags or [],
                    "columns_profile": columns_profile or [],
                    "status": row[11],
                    "error_message": row[12],
                    "confidence_score": row[13],
                    "is_temporary": row[14],
                    "is_ignored": row[15],
                    "confidence_reason": row[16],
                    "created_at": row[17],
                    "updated_at": row[18],
                })
        return profiles

    @staticmethod
    async def get_table_profile(source_id: int, table_name: str) -> Optional[Dict[str, Any]]:
        """获取单张表的摸排画像"""
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT id, connection_id, table_name, table_type, engine, ddl, sample_data,
                           ai_term, ai_description, ai_tags, columns_profile, status, error_message,
                           confidence_score, is_temporary, is_ignored, confidence_reason, created_at, updated_at
                    FROM db_table_profiles
                    WHERE connection_id = %s AND table_name = %s
                    LIMIT 1
                    """,
                    (source_id, table_name),
                )
                row = await cursor.fetchone()

        if not row:
            return None

        sample_data = DbProfileService._parse_json_field(row[6], row[6])
        ai_tags = DbProfileService._parse_json_field(row[9], [])
        columns_profile = DbProfileService._parse_json_field(row[10], [])
        return {
            "id": row[0],
            "connection_id": row[1],
            "table_name": row[2],
            "table_type": row[3],
            "engine": row[4],
            "ddl": row[5],
            "sample_data": sample_data,
            "ai_term": row[7],
            "ai_description": row[8],
            "ai_tags": ai_tags or [],
            "columns_profile": columns_profile or [],
            "status": row[11],
            "error_message": row[12],
            "confidence_score": row[13],
            "is_temporary": row[14],
            "is_ignored": row[15],
            "confidence_reason": row[16],
            "created_at": row[17],
            "updated_at": row[18],
        }

    @staticmethod
    def build_profile_ai_context(profile: Dict[str, Any]) -> str:
        """将摸排画像组装为 AI 可用的 schema 上下文"""
        import json as _json

        lines = [
            f"表名: {profile.get('table_name', '')}",
            f"类型: {profile.get('table_type', 'TABLE')}",
        ]
        if profile.get("ai_term"):
            lines.append(f"业务术语: {profile['ai_term']}")
        if profile.get("ai_description"):
            lines.append(f"用途描述: {profile['ai_description']}")
        tags = profile.get("ai_tags") or []
        if isinstance(tags, list) and tags:
            lines.append(f"分类标签: {', '.join(str(t) for t in tags)}")
        if profile.get("confidence_score") is not None:
            lines.append(f"分析置信度: {profile['confidence_score']}%")
        if profile.get("confidence_reason"):
            lines.append(f"置信说明: {profile['confidence_reason']}")

        columns_profile = profile.get("columns_profile") or []
        if columns_profile:
            lines.append("\n字段画像:")
            for col in columns_profile:
                name = col.get("name", "")
                term = col.get("term") or "-"
                desc = col.get("desc") or "-"
                lines.append(f"  - {name}: {term} | {desc}")

        if profile.get("ddl"):
            lines.append(f"\n建表 DDL:\n{profile['ddl']}")

        sample_data = profile.get("sample_data")
        if sample_data:
            if not isinstance(sample_data, str):
                sample_data = _json.dumps(sample_data, ensure_ascii=False)
            lines.append(f"\n样例数据:\n{sample_data[:2000]}")

        return "\n".join(lines)

    @staticmethod
    async def run_profiling_loop(source_id: int):
        """后台串行分析摸排主循环 (以单线程逐表异步执行)"""
        logger.info(f"[DbProfiling] Starting background profiling task for source_id: {source_id}")
        try:
            # 1. 取得数据源配置与待分析表列表
            datasource = await DataSourceService.get_datasource(source_id)
            if not datasource:
                logger.error(f"[DbProfiling] Data Source {source_id} not found, exiting.")
                return

            from app.services.data_adapter.factory import get_adapter
            adapter = await get_adapter(datasource.source_name)

            async with get_db_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT table_name, table_type
                        FROM db_table_profiles
                        WHERE connection_id = %s AND status = 0
                        ORDER BY table_name ASC
                        """,
                        (source_id,)
                    )
                    pending_rows = await cursor.fetchall()
            
            pending_tables = [{"table_name": r[0], "table_type": r[1]} for r in pending_rows]
            total_tables = len(pending_tables)

            task_status = await DbProfileService.get_task_status(source_id)
            total_all_tables = task_status.get("total_tables", total_tables) if task_status else total_tables
            completed_before = task_status.get("processed_tables", 0) if task_status else 0

            logger.info(
                f"[DbProfiling] Connection {source_id} has {total_tables} pending tables "
                f"({completed_before}/{total_all_tables} already done)."
            )

            # 2. 逐表处理
            for idx, table in enumerate(pending_tables):
                if await DbProfileService._should_stop_profiling(source_id):
                    logger.info(
                        f"[DbProfiling] Profiling task stop requested for source_id: {source_id}, "
                        f"exiting after {completed_before + idx}/{total_all_tables} tables."
                    )
                    return

                table_name = table["table_name"]
                table_type = table["table_type"]
                logger.info(
                    f"[DbProfiling] [{completed_before + idx + 1}/{total_all_tables}] "
                    f"Profiling table: {table_name}"
                )

                # 更新主任务状态为当前正在分析的表
                async with get_db_connection() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(
                            """
                            UPDATE db_profile_tasks
                            SET processed_tables = %s, current_table = %s, updated_at = NOW()
                            WHERE connection_id = %s
                            """,
                            (completed_before + idx, table_name, source_id)
                        )
                        await cursor.execute(
                            """
                            UPDATE db_table_profiles
                            SET status = 1, updated_at = NOW()
                            WHERE connection_id = %s AND table_name = %s
                            """,
                            (source_id, table_name)
                        )
                        await conn.commit()

                # 执行 DDL 与 数据采样抓取
                try:
                    db_type = datasource.source_type.strip().lower()
                    
                    # 1) 获取 DDL
                    ddl = await DbProfileService._get_table_ddl(adapter, db_type, table_name, table_type)

                    # 2) 样例抓取 (SELECT LIMIT 3，跳过大字段类型)
                    sample_data_json = "[]"
                    try:
                        query_sql = await DbProfileService._build_sample_query(
                            adapter, db_type, table_name
                        )
                        sample_res = await adapter.execute_sql(query_sql)
                        rows = sample_res.get("items") or sample_res.get("rows") or []
                        cols = sample_res.get("columns", [])

                        # 敏感长字段防溢出截断
                        sanitized_rows = []
                        for row in rows:
                            new_row = []
                            for val in row:
                                if isinstance(val, str) and len(val) > 150:
                                    new_row.append(val[:150] + "...")
                                else:
                                    new_row.append(val)
                            sanitized_rows.append(new_row)

                        sample_dicts = []
                        for row in sanitized_rows:
                            col_names = [c["name"] if isinstance(c, dict) else str(c) for c in cols]
                            sample_dicts.append(dict(zip(col_names, row)))

                        import decimal
                        from datetime import date, datetime

                        class _SafeEncoder(json.JSONEncoder):
                            def default(self, obj):
                                if isinstance(obj, (datetime, date)):
                                    return obj.isoformat()
                                if isinstance(obj, decimal.Decimal):
                                    return float(obj)
                                if isinstance(obj, bytes):
                                    return obj.decode("utf-8", errors="replace")
                                return str(obj)

                        sample_data_json = json.dumps(sample_dicts, cls=_SafeEncoder, ensure_ascii=False)
                    except Exception as ex_sample:
                        logger.warning(f"[DbProfiling] Failed to fetch sample data for {table_name}: {ex_sample}")
                        sample_data_json = "[]"

                    # 3) 直接调用 LLM 进行推断
                    ai_res = await DbProfileService._analyze_table_with_llm(ddl, sample_data_json)

                    # 4) 后处理：综合规则修正与打分
                    llm_score = ai_res.get("confidence_score")
                    if llm_score is None:
                        llm_score = 100
                    try:
                        llm_score = int(llm_score)
                    except (ValueError, TypeError):
                        llm_score = 90
                    
                    llm_temp = 1 if ai_res.get("is_temporary") is True else 0
                    llm_reason = ai_res.get("confidence_reason") or ""

                    # 硬规则 1: 采样数据空检测
                    is_sample_empty = False
                    try:
                        parsed_samples = json.loads(sample_data_json)
                        if not parsed_samples:
                            is_sample_empty = True
                    except Exception:
                        is_sample_empty = True
                    
                    if is_sample_empty:
                        llm_score = max(0, llm_score - 30)
                        llm_reason += "; [特征检测] 样例数据为空，扣除30分"

                    # 硬规则 2: 表名敏感词匹配
                    sensitive_patterns = [r"^tmp_", r"^temp_", r"_bak$", r"_bak_", r"^test_"]
                    is_name_sensitive = any(re.search(pat, table_name.lower()) for pat in sensitive_patterns)
                    if is_name_sensitive:
                        llm_score = max(0, llm_score - 40)
                        llm_temp = 1
                        llm_reason += "; [特征检测] 表名匹配临时/备份敏感词，扣除40分"

                    # 限制评分区间为 [0, 100]
                    llm_score = min(100, max(0, llm_score))

                    # 决策忽略状态：评分低于 60 分或标记为临时表，则默认置为忽略
                    is_ignored = 1 if (llm_score < 60 or llm_temp == 1) else 0

                    ai_tags_str = json.dumps(ai_res.get("ai_tags") or [])
                    columns_profile_str = json.dumps(ai_res.get("columns") or [])

                    # 5) 成功回填
                    async with get_db_connection() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute(
                                """
                                UPDATE db_table_profiles
                                SET ddl = %s, sample_data = %s, ai_term = %s, ai_description = %s,
                                    ai_tags = %s, columns_profile = %s, confidence_score = %s,
                                    is_temporary = %s, is_ignored = %s, confidence_reason = %s,
                                    status = 2, error_message = NULL, updated_at = NOW()
                                WHERE connection_id = %s AND table_name = %s
                                """,
                                (
                                    ddl, sample_data_json, ai_res.get("ai_term"), ai_res.get("ai_description"),
                                    ai_tags_str, columns_profile_str, llm_score,
                                    llm_temp, is_ignored, llm_reason.strip("; "),
                                    source_id, table_name
                                )
                            )
                            await conn.commit()

                except Exception as ex_item:
                    logger.exception(f"[DbProfiling] Table {table_name} profiling failed")
                    async with get_db_connection() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute(
                                """
                                UPDATE db_table_profiles
                                SET status = 3, error_message = %s, updated_at = NOW()
                                WHERE connection_id = %s AND table_name = %s
                                """,
                                (str(ex_item), source_id, table_name)
                            )
                            await conn.commit()

            if await DbProfileService._should_stop_profiling(source_id):
                logger.info(f"[DbProfiling] Profiling task cancelled before finalize for source_id: {source_id}")
                return

            # 3. 完成所有表后，将主任务置为成功 (2)
            async with get_db_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        UPDATE db_profile_tasks
                        SET status = 2, processed_tables = %s, current_table = NULL, updated_at = NOW()
                        WHERE connection_id = %s AND status = 1
                        """,
                        (total_all_tables, source_id)
                    )
                    await conn.commit()
            logger.info(f"[DbProfiling] Finished background profiling task for source_id: {source_id}")

        except Exception as total_ex:
            logger.exception(f"[DbProfiling] Fatal error in profiling task for datasource {source_id}")
            async with get_db_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        UPDATE db_profile_tasks
                        SET status = 3, error_message = %s, current_table = NULL, updated_at = NOW()
                        WHERE connection_id = %s
                        """,
                        (str(total_ex), source_id)
                    )
                    await conn.commit()
        finally:
            try:
                await DbProfileService.reconcile_profiling_task_status(source_id)
            except Exception:
                logger.exception(
                    "[DbProfiling] Failed to reconcile profiling task status for source_id=%s",
                    source_id,
                )

    @staticmethod
    async def _get_table_ddl(adapter, db_type: str, table_name: str, table_type: str) -> str:
        """获取特定引擎特定表的建表 DDL"""
        async def parse_lob(val):
            if val is None:
                return ""
            if hasattr(val, "read"):
                res = val.read()
                if inspect.isawaitable(res):
                    return await res
                return res
            return str(val)

        if db_type == "mysql":
            res = await adapter.execute_sql(f"SHOW CREATE TABLE `{table_name}`")
            rows = res.get("items") or res.get("rows") if res else []
            if rows:
                return str(rows[0][1]) + ";"
            return ""
        elif db_type == "clickhouse":
            res = await adapter.execute_sql(f"SHOW CREATE TABLE `{table_name}`")
            rows = res.get("items") or res.get("rows") if res else []
            if rows:
                return str(rows[0][0]) + ";"
            return ""
        elif db_type == "oracle":
            obj_type = "VIEW" if "VIEW" in table_type.upper() else "TABLE"
            sql = f"SELECT DBMS_METADATA.GET_DDL('{obj_type}', '{table_name.upper()}') FROM DUAL"
            res = await adapter.execute_sql(sql)
            rows = res.get("items") or res.get("rows") if res else []
            if rows:
                lob_val = rows[0][0]
                ddl_str = await parse_lob(lob_val)
                return ddl_str.strip()
            return ""
        elif db_type in ("sqlserver", "mssql", "tsql"):
            if "VIEW" in table_type.upper():
                sql = """
                    SELECT m.definition
                    FROM sys.sql_modules m
                    INNER JOIN sys.objects o ON m.object_id = o.object_id
                    WHERE o.name = :name AND o.type = 'V'
                """
                res = await adapter.execute_sql(sql, {"name": table_name})
                rows = res.get("items") or res.get("rows") if res else []
                if rows:
                    return str(rows[0][0]).strip()
                return ""
            else:
                # 拼装 SQL Server 表结构 DDL
                sql = """
                    SELECT
                        COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH,
                        NUMERIC_PRECISION, NUMERIC_SCALE, IS_NULLABLE, COLUMN_DEFAULT
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = :name AND TABLE_CATALOG = DB_NAME()
                    ORDER BY ORDINAL_POSITION
                """
                res = await adapter.execute_sql(sql, {"name": table_name})
                rows = res.get("items") or res.get("rows") if res else []
                if not rows:
                    return ""
                
                col_defs = []
                for row in rows:
                    col_name, data_type, char_len, num_precision, num_scale, is_nullable, col_default = row
                    data_type = (data_type or "").lower()
                    
                    # 格式化数据类型
                    if data_type in ("varchar", "nvarchar", "char", "nchar") and char_len:
                        col_type = f"{data_type}(max)" if int(char_len) == -1 else f"{data_type}({int(char_len)})"
                    elif data_type in ("decimal", "numeric") and num_precision is not None:
                        scale = int(num_scale or 0)
                        col_type = f"{data_type}({int(num_precision)},{scale})"
                    else:
                        col_type = data_type
                        
                    nullable = "" if is_nullable == "NO" else " NULL"
                    default = f" DEFAULT {col_default}" if col_default else ""
                    col_defs.append(f"    [{col_name}] {col_type}{nullable}{default}")
                return f"CREATE TABLE [{table_name}] (\n" + ",\n".join(col_defs) + "\n);"
        else:
            raise ValueError(f"不支持获取 DDL 的引擎类型: {db_type}")

    @staticmethod
    async def _analyze_table_with_llm(ddl: str, sample_data_json: str) -> Dict[str, Any]:
        """直接调用底层大模型解析元数据"""
        system_prompt = (
            "你是一个精通数据资产治理的数据库专家，擅长从建表语句和样例数据中提炼业务元数据含义。\n"
            "请根据提供的【建表 DDL】和【真实样例数据】，推测该表的中文业务术语（备注名）、表的一句话用途描述、表的分类标签，以及每个字段的中文术语和字段业务描述。\n"
            "同时，你需要深度评估该表对于业务分析的“置信度（即数据分析价值与可信度得分）”，以及它是否属于临时/低价值/中间关联表。\n\n"
            "【置信度与临时表评估标准】\n"
            "1. 若建表语句和样例数据表明该表主要为关联ID中间映射（例如只有各种id字段而无具体业务度量或名称维度）、临时缓存/计算中间表、系统备份表（如表名中含有 tmp, temp, bak, test 等），或样例内容缺乏真实语义关联，应标记 is_temporary 为 true，置信度评分 confidence_score 应低于 60 分。\n"
            "2. 若表结构包含有意义的业务属性、主数据维度或事实度量，有实际分析价值，应标记 is_temporary 为 false，置信度评分应为 80-100 分。\n"
            "3. 需给出客观、具体的扣分或评分理由（confidence_reason）。\n\n"
            "【重要约束】\n"
            "1. 必须只返回一个 JSON 对象，不要 Markdown，不要多余解释。\n"
            "2. 返回的 JSON 必须符合以下 Schema 结构：\n"
            "{\n"
            '  "ai_term": "表的中文业务备注名，不超过100字，如: 机房能耗天报表",\n'
            '  "ai_description": "该表真实的业务用途与功能描述，不超过500字",\n'
            '  "ai_tags": ["标签1", "标签2"],\n'
            '  "confidence_score": 85,\n'
            '  "is_temporary": false,\n'
            '  "confidence_reason": "评分和临时表认定的理由说明，不超过200字，如: 结构完整且含真实指标数据，但主键不明确扣减10分",\n'
            '  "columns": [\n'
            "    {\n"
            '      "name": "字段物理列名，如 room_id",\n'
            '      "term": "字段的中文业务术语/备注名，如 机房ID",\n'
            '      "desc": "该字段的业务解释描述"\n'
            "    }\n"
            "  ]\n"
            "}\n"
        )

        user_prompt = f"【建表 DDL】:\n{ddl}\n\n【样例数据】:\n{sample_data_json}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response_text = await AIService.chat_completion(messages)
        if not response_text:
            raise ValueError("LLM 返回空响应")
            
        return DbProfileService._extract_json(response_text)

    @staticmethod
    def _extract_json(raw: str) -> Dict[str, Any]:
        """提取并解析返回的 JSON 内容"""
        text = (raw or "").strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```json") or lines[0].startswith("```"):
                text = "\n".join(lines[1:-1]).strip()
        try:
            return json.loads(text)
        except Exception:
            # 兼容 LLM 输出中可能存在的 markdown 标签包裹
            match = re.search(r"\{[\s\S]*\}", text)
            if not match:
                raise ValueError(f"大模型返回内容无法解析为JSON: {raw}")
            return json.loads(match.group())

    @staticmethod
    async def toggle_ignore(
        source_id: int,
        table_name: str,
        is_ignored: int
    ) -> Optional[Dict[str, Any]]:
        """手动更改指定物理表的忽略状态"""
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT is_ignored FROM db_table_profiles
                    WHERE connection_id = %s AND table_name = %s
                    """,
                    (source_id, table_name)
                )
                existing = await cursor.fetchone()
                if not existing:
                    return None
                
                next_val = 1 if is_ignored == 1 else 0
                await cursor.execute(
                    """
                    UPDATE db_table_profiles
                    SET is_ignored = %s, updated_at = NOW()
                    WHERE connection_id = %s AND table_name = %s
                    """,
                    (next_val, source_id, table_name)
                )
                await conn.commit()
                
                return {"table_name": table_name, "is_ignored": next_val}
