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


class DbProfileService:
    """外部数据源元数据智能摸排与分析服务"""

    @staticmethod
    async def trigger_profiling_task(
        source_id: int,
        background_tasks: BackgroundTasks
    ) -> Dict[str, Any]:
        """
        触发该数据源配置下所有表和视图的智能分析摸排后台任务（一个数据源只允许一个进行中的任务）
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
                
                if existing_task and existing_task[1] == 1:
                    raise ValueError("当前数据源分析摸排任务正在执行中，请勿重复点击")

                # 3. 实例化适配器并查询数据库下所有的表/视图
                from app.services.data_adapter.factory import get_adapter
                adapter = await get_adapter(datasource.source_name)
                tables_info = await adapter.get_tables()
                total_count = len(tables_info)

                # 4. Upsert 主任务状态
                if existing_task:
                    await cursor.execute(
                        """
                        UPDATE db_profile_tasks
                        SET status = 1, total_tables = %s, processed_tables = 0,
                            current_table = NULL, error_message = NULL, updated_at = NOW()
                        WHERE connection_id = %s
                        """,
                        (total_count, source_id)
                    )
                else:
                    await cursor.execute(
                        """
                        INSERT INTO db_profile_tasks (connection_id, status, total_tables, processed_tables)
                        VALUES (%s, 1, %s, 0)
                        """,
                        (source_id, total_count)
                    )

                # 5. 准备并初始化子表记录 (db_table_profiles)
                await cursor.execute(
                    "SELECT id, table_name FROM db_table_profiles WHERE connection_id = %s",
                    (source_id,)
                )
                sub_rows = await cursor.fetchall()
                existing_profiles = {row[1]: row[0] for row in sub_rows}

                active_table_names = {t["name"] for t in tables_info}

                # 清除已物理不存在的表的草稿
                for t_name, p_id in list(existing_profiles.items()):
                    if t_name not in active_table_names:
                        await cursor.execute("DELETE FROM db_table_profiles WHERE id = %s", (p_id,))
                        del existing_profiles[t_name]

                # 初始化待处理状态
                for t in tables_info:
                    t_name = t["name"]
                    t_type = t.get("type", "table").lower()
                    if t_name in existing_profiles:
                        await cursor.execute(
                            """
                            UPDATE db_table_profiles
                            SET status = 0, error_message = NULL, table_type = %s, updated_at = NOW()
                            WHERE connection_id = %s AND table_name = %s
                            """,
                            (t_type, source_id, t_name)
                        )
                    else:
                        await cursor.execute(
                            """
                            INSERT INTO db_table_profiles (connection_id, table_name, table_type, status)
                            VALUES (%s, %s, %s, 0)
                            """,
                            (source_id, t_name, t_type)
                        )
                
                await conn.commit()

        # 6. 加入 FastAPI 后台任务
        background_tasks.add_task(DbProfileService.run_profiling_loop, source_id)
        
        # 重新查询当前任务对象返回
        return await DbProfileService.get_task_status(source_id)

    @staticmethod
    async def get_task_status(source_id: int) -> Optional[Dict[str, Any]]:
        """获取该数据源当前摸排任务进度与状态"""
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
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
                    return None
                return {
                    "id": row[0],
                    "connection_id": row[1],
                    "status": row[2],
                    "total_tables": row[3],
                    "processed_tables": row[4],
                    "current_table": row[5],
                    "error_message": row[6],
                    "created_at": row[7],
                    "updated_at": row[8]
                }

    @staticmethod
    async def list_table_profiles(source_id: int) -> List[Dict[str, Any]]:
        """获取该数据源下已摸排/分析的表画像列表"""
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT id, connection_id, table_name, table_type, engine, ddl, sample_data,
                           ai_term, ai_description, ai_tags, columns_profile, status, error_message,
                           confidence_score, is_temporary, is_ignored, confidence_reason, created_at, updated_at
                    FROM db_table_profiles
                    WHERE connection_id = %s
                    ORDER BY table_name ASC
                    """,
                    (source_id,)
                )
                rows = await cursor.fetchall()
                
                profiles = []
                for row in rows:
                    sample_data = row[6]
                    if sample_data and isinstance(sample_data, str):
                        try:
                            sample_data = json.loads(sample_data)
                        except Exception:
                            pass
                            
                    ai_tags = row[9]
                    if ai_tags and isinstance(ai_tags, str):
                        try:
                            ai_tags = json.loads(ai_tags)
                        except Exception:
                            ai_tags = []
                            
                    columns_profile = row[10]
                    if columns_profile and isinstance(columns_profile, str):
                        try:
                            columns_profile = json.loads(columns_profile)
                        except Exception:
                            columns_profile = []

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
                        "updated_at": row[18]
                    })
                return profiles

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
            logger.info(f"[DbProfiling] Connection {source_id} has {total_tables} tables to analyze.")

            # 2. 逐表处理
            for idx, table in enumerate(pending_tables):
                table_name = table["table_name"]
                table_type = table["table_type"]
                logger.info(f"[DbProfiling] [{idx + 1}/{total_tables}] Profiling table: {table_name}")

                # 更新主任务状态为当前正在分析的表
                async with get_db_connection() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(
                            """
                            UPDATE db_profile_tasks
                            SET processed_tables = %s, current_table = %s, updated_at = NOW()
                            WHERE connection_id = %s
                            """,
                            (idx, table_name, source_id)
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

                    # 2) 样例抓取 (SELECT LIMIT 3)
                    sample_data_json = "[]"
                    try:
                        quote = "`" if db_type in ("mysql", "clickhouse") else '"'
                        if db_type == "oracle":
                            query_sql = f"SELECT * FROM {quote}{table_name.upper()}{quote} WHERE ROWNUM <= 3"
                        elif db_type in ("sqlserver", "mssql", "tsql"):
                            query_sql = f"SELECT TOP 3 * FROM {quote}{table_name}{quote}"
                        else:
                            query_sql = f"SELECT * FROM {quote}{table_name}{quote} LIMIT 3"
                        
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

            # 3. 完成所有表后，将主任务置为成功 (2)
            async with get_db_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        UPDATE db_profile_tasks
                        SET status = 2, processed_tables = %s, current_table = NULL, updated_at = NOW()
                        WHERE connection_id = %s
                        """,
                        (total_tables, source_id)
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
