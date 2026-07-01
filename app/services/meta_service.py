import json
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.core.database import get_db_connection
from app.core import redis
from app.schemas.resource import ResourceCreate, ResourceUpdate, ResourceResponse
from app.services.resource_version_service import ResourceVersionService, SNAPSHOT_FIELDS
import logging

logger = logging.getLogger(__name__)

class MetaService:
    CACHE_KEY_PREFIX = "yunshu:meta:config:"
    CACHE_TTL = 3600 # 1 hour
    SYSTEM_RESOURCE_GROUP = "System"

    @classmethod
    def _assert_assignable_resource_group(cls, resource_group: str, resource_key: Optional[str] = None) -> None:
        if resource_group.strip().lower() != cls.SYSTEM_RESOURCE_GROUP.lower():
            return
        if resource_key and resource_key.startswith('system.'):
            return
        raise ValueError("'System' 分组为系统内置，不可用于普通资源")

    @classmethod
    async def get_config(cls, resource_key: str) -> Optional[ResourceResponse]:
        """Get resource configuration by key."""
        cache_key = f"{cls.CACHE_KEY_PREFIX}{resource_key}"
        try:
            r = await redis.get_redis()
            if r:
                cached_data = await r.get(cache_key)
                if cached_data:
                    return ResourceResponse(**json.loads(cached_data))
        except Exception: pass

        config = await cls._fetch_from_db(resource_key)
        if config:
            try:
                r = await redis.get_redis()
                if r:
                    await r.setex(cache_key, cls.CACHE_TTL, json.dumps(config.dict(), default=str))
            except Exception: pass
        return config

    @classmethod
    async def invalidate_cache(cls, resource_key: str):
        """Invalidate cache for a specific resource."""
        cache_key = f"{cls.CACHE_KEY_PREFIX}{resource_key}"
        try:
            r = await redis.get_redis()
            if r: await r.delete(cache_key)
        except Exception: pass

    @classmethod
    async def _fetch_from_db(cls, resource_key: str) -> Optional[ResourceResponse]:
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT id, resource_key, resource_name, resource_group, data_source, 
                           resource_mode, table_name, custom_sql, fields_config, 
                           allowed_filters, default_sort, status, created_at, updated_at, remarks,
                           (SELECT COUNT(*) FROM sys_user_resources WHERE resource_key = sys_resource_meta.resource_key) as reference_count,
                           cache_ttl
                    FROM sys_resource_meta
                    WHERE resource_key = %s
                    """, (resource_key,)
                )
                row = await cursor.fetchone()
                if row: return cls._map_row_to_model(row)

        if resource_key == 'system.sql.execute':
            return ResourceResponse(
                id=999999, resource_key="system.sql.execute", resource_name="动态 SQL 查询",
                resource_group="System", data_source="default", resource_mode="SYSTEM",
                table_name=None, custom_sql=None, fields_config=[], allowed_filters=[],
                default_sort="", status=1, created_at=datetime.now(), updated_at=datetime.now(),
                remarks="系统内置", reference_count=0, cache_ttl=30
            )
        return None

    @staticmethod
    def _map_row_to_model(row: tuple) -> ResourceResponse:
        (id, r_key, r_name, r_group, ds, r_mode, t_name, c_sql, f_cfg, a_filt, d_sort, status, c_at, u_at, rem, ref_c, c_ttl) = row
        if f_cfg is None: f_cfg = []
        elif isinstance(f_cfg, str): f_cfg = json.loads(f_cfg)
        if a_filt is None: a_filt = []
        elif isinstance(a_filt, str): a_filt = json.loads(a_filt)
        return ResourceResponse(
            id=id, resource_key=r_key, resource_name=r_name, resource_group=r_group, data_source=ds,
            resource_mode=r_mode, table_name=t_name, custom_sql=c_sql, fields_config=f_cfg,
            allowed_filters=a_filt, default_sort=d_sort, status=status, created_at=c_at, updated_at=u_at,
            remarks=rem, reference_count=ref_c, cache_ttl=c_ttl or 0
        )

    @classmethod
    async def list_resources(cls) -> List[ResourceResponse]:
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT id, resource_key, resource_name, resource_group, data_source, resource_mode, table_name, custom_sql, fields_config, allowed_filters, default_sort, status, created_at, updated_at, remarks, (SELECT COUNT(*) FROM sys_user_resources WHERE resource_key = sys_resource_meta.resource_key) as reference_count, cache_ttl FROM sys_resource_meta ORDER BY id DESC")
                resources = [cls._map_row_to_model(row) for row in await cursor.fetchall()]
                if not any(r.resource_key == 'system.sql.execute' for r in resources):
                    resources.append(await cls._fetch_from_db('system.sql.execute'))
                return resources

    @classmethod
    async def get_user_resources(cls, user_id: int) -> List[ResourceResponse]:
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT m.*, (SELECT COUNT(*) FROM sys_user_resources WHERE resource_key = m.resource_key) as reference_count FROM sys_resource_meta m JOIN sys_user_resources ur ON m.resource_key = ur.resource_key WHERE ur.user_id = %s ORDER BY m.id DESC", (user_id,))
                # Row mapping for this custom JOIN query might need adjustment depending on column order
                # For safety, fetch all fields from meta explicitly
                sql = """
                    SELECT m.id, m.resource_key, m.resource_name, m.resource_group, m.data_source, 
                           m.resource_mode, m.table_name, m.custom_sql, m.fields_config, 
                           m.allowed_filters, m.default_sort, m.status, m.created_at, m.updated_at, m.remarks,
                           (SELECT COUNT(*) FROM sys_user_resources WHERE resource_key = m.resource_key) as reference_count,
                           m.cache_ttl
                    FROM sys_resource_meta m
                    JOIN sys_user_resources ur ON m.resource_key = ur.resource_key
                    WHERE ur.user_id = %s
                    ORDER BY m.id DESC
                """
                await cursor.execute(sql, (user_id,))
                return [cls._map_row_to_model(row) for row in await cursor.fetchall()]

    @classmethod
    async def create_resource(
        cls,
        resource: ResourceCreate,
        operator: Optional[Dict[str, Any]] = None,
    ) -> ResourceResponse:
        cls._assert_assignable_resource_group(resource.resource_group)
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO sys_resource_meta (resource_key, resource_name, resource_group, data_source, resource_mode, table_name, custom_sql, fields_config, allowed_filters, default_sort, status, remarks, cache_ttl) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (resource.resource_key, resource.resource_name, resource.resource_group, resource.data_source, resource.resource_mode, resource.table_name, resource.custom_sql, json.dumps([f.dict() for f in resource.fields_config]), json.dumps([f.dict() for f in resource.allowed_filters]), resource.default_sort, resource.status, resource.remarks, resource.cache_ttl)
                )
                await conn.commit()
        created = await cls._fetch_from_db(resource.resource_key)
        if created:
            try:
                await ResourceVersionService.record_version(
                    created, "CREATE", operator, "初始创建"
                )
            except Exception as e:
                logger.warning("Failed to record resource create version: %s", e)
        return created

    @classmethod
    async def update_resource(
        cls,
        resource_key: str,
        update_data: ResourceUpdate,
        operator: Optional[Dict[str, Any]] = None,
        action_type: str = "UPDATE",
        change_summary: Optional[str] = None,
    ) -> Optional[ResourceResponse]:
        update_dict = update_data.dict(exclude_unset=True)
        if not update_dict:
            return await cls.get_config(resource_key)

        existing = await cls.get_config(resource_key)
        if not existing:
            return None

        if change_summary is None and action_type == "UPDATE":
            change_summary = ResourceVersionService.compute_change_summary(existing, update_dict)

        if 'resource_group' in update_dict:
            cls._assert_assignable_resource_group(update_dict['resource_group'], resource_key)
        set_clauses = []; values = []
        for k, v in update_dict.items():
            if k in ('fields_config', 'allowed_filters'): v = json.dumps(v)
            set_clauses.append(f"{k} = %s"); values.append(v)
        values.append(resource_key)
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(f"UPDATE sys_resource_meta SET {', '.join(set_clauses)} WHERE resource_key = %s", tuple(values))
                await conn.commit()
        await cls.invalidate_cache(resource_key)
        updated = await cls._fetch_from_db(resource_key)
        if updated:
            version_id = None
            try:
                version_id = await ResourceVersionService.record_version(
                    updated, action_type, operator, change_summary
                )
            except Exception as e:
                logger.warning("Failed to record resource update version: %s", e)
            if version_id and action_type in ("UPDATE", "ROLLBACK"):
                try:
                    from app.services.catalog_change_notification_service import (
                        CatalogChangeNotificationService,
                    )

                    await CatalogChangeNotificationService.notify_on_resource_change(
                        resource_key=resource_key,
                        resource_name=updated.resource_name,
                        version_id=version_id,
                        action_type=action_type,
                        change_summary=change_summary,
                        operator=operator,
                    )
                except Exception as e:
                    logger.warning("Failed to notify catalog resource change: %s", e)
        return updated

    @classmethod
    async def rollback_resource(
        cls,
        resource_key: str,
        version_id: int,
        operator: Optional[Dict[str, Any]] = None,
    ) -> Optional[ResourceResponse]:
        rollback_data = await ResourceVersionService.get_snapshot_for_rollback(version_id)
        if not rollback_data:
            return None
        target_key, snapshot, version_no = rollback_data
        if target_key != resource_key:
            return None

        update_payload = {
            field: snapshot.get(field)
            for field in SNAPSHOT_FIELDS
            if field != "resource_key" and field in snapshot
        }
        return await cls.update_resource(
            resource_key,
            ResourceUpdate(**update_payload),
            operator=operator,
            action_type="ROLLBACK",
            change_summary=f"回滚至版本 v{version_no}",
        )

    @classmethod
    async def delete_resource(cls, resource_key: str) -> bool:
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("DELETE FROM sys_resource_meta WHERE resource_key = %s", (resource_key,))
                await conn.commit()
                if cursor.rowcount > 0:
                    await cls.invalidate_cache(resource_key); return True
                return False

    @staticmethod
    async def get_tables(data_source: str = "default_clickhouse") -> List[Dict[str, str]]:
        from app.services.data_adapter.factory import get_adapter
        return await (await get_adapter(data_source)).get_tables()

    @staticmethod
    async def enrich_tables_with_metadata(data_source: str, tables: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Merge meta_tables.term into table list for UI display."""
        if not tables:
            return tables
        term_map: Dict[str, str] = {}
        try:
            async with get_db_connection() as conn:
                import aiomysql
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(
                        """
                        SELECT t.physical_name, t.term
                        FROM meta_tables t
                        JOIN meta_datasets d ON t.dataset_id = d.id
                        WHERE d.data_source = %s AND t.term IS NOT NULL AND t.term != ''
                        """,
                        (data_source,),
                    )
                    for row in await cursor.fetchall():
                        term_map[row["physical_name"].lower()] = row["term"]
        except Exception as e:
            logger.warning("Failed to enrich tables with metadata terms: %s", e)
            return tables

        enriched: List[Dict[str, str]] = []
        for table in tables:
            entry = dict(table)
            term = term_map.get(entry["name"].lower())
            if term:
                entry["term"] = term
            enriched.append(entry)
        return enriched

    @staticmethod
    async def enrich_columns_with_metadata(
        data_source: str,
        table_name: Optional[str],
        columns: List[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        """Merge meta_columns.term into column list; metadata term overrides DB comment."""
        if not table_name or not columns:
            return columns
        term_map: Dict[str, str] = {}
        try:
            async with get_db_connection() as conn:
                import aiomysql
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(
                        """
                        SELECT c.physical_name, c.term
                        FROM meta_columns c
                        JOIN meta_tables t ON c.table_id = t.id
                        JOIN meta_datasets d ON t.dataset_id = d.id
                        WHERE d.data_source = %s AND t.physical_name = %s
                          AND c.term IS NOT NULL AND c.term != ''
                        """,
                        (data_source, table_name),
                    )
                    for row in await cursor.fetchall():
                        term_map[row["physical_name"].lower()] = row["term"]
        except Exception as e:
            logger.warning("Failed to enrich columns with metadata terms: %s", e)
            return columns

        enriched: List[Dict[str, str]] = []
        for column in columns:
            entry = dict(column)
            term = term_map.get(entry["name"].lower())
            if term:
                entry["comment"] = term
            enriched.append(entry)
        return enriched

    @staticmethod
    async def get_columns(data_source: str, table_name: Optional[str] = None, custom_sql: Optional[str] = None, params: Optional[dict] = None) -> List[Dict[str, str]]:
        from app.services.data_adapter.factory import get_adapter
        return await (await get_adapter(data_source)).get_columns(table_name=table_name, custom_sql=custom_sql, params=params)

    @staticmethod
    async def get_adapter_by_id(source_id: int):
        from app.services.datasource_service import DataSourceService
        from app.services.data_adapter.factory import get_adapter
        datasource = await DataSourceService.get_datasource(source_id)
        if not datasource: raise ValueError(f"Data source ID {source_id} not found")
        return await get_adapter(datasource.source_name)

    @staticmethod
    async def get_recommendation_context(source_id: int, tables: Optional[List[str]] = None) -> str:
        """为 AI 一键推荐场景获取上下文。优先质量最高的表和指标。"""
        from app.services.datasource_service import DataSourceService
        from app.services.metadata_v2_service import MetadataV2Service
        from app.services.metadata_yaml_service import MetadataYamlService
        
        datasource = await DataSourceService.get_datasource(source_id)
        if not datasource: return ""

        target_tables = list(tables) if (tables and len(tables) > 0) else []
        
        # 1. 如果没选表，自动筛选“高质量”资产
        if not target_tables:
            async with get_db_connection() as conn:
                import aiomysql
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # 筛选策略：优先有业务术语、有指标的表。
                    # 增加权重：有指标的表质量通常极高
                    sql = """
                        SELECT t.physical_name, t.id,
                               ((CASE WHEN t.term IS NOT NULL AND t.term != '' THEN 5 ELSE 0 END) + 
                               ((SELECT COUNT(*) FROM meta_metrics WHERE dataset_id = t.dataset_id) * 3)) as quality_score
                        FROM meta_tables t
                        JOIN meta_datasets d ON t.dataset_id = d.id
                        WHERE d.data_source = %s
                        ORDER BY quality_score DESC, t.id ASC
                        LIMIT 8
                    """
                    await cursor.execute(sql, (datasource.source_name,))
                    rows = await cursor.fetchall()
                    target_tables = [r['physical_name'] for r in rows]
        else:
            logger.info(f"AI Recommendation focused on {len(target_tables)} user-selected tables")

        if not target_tables: return ""

        # 2. 批量获取并组装 YAML
        results = []
        for table_name in target_tables:
            try:
                async with get_db_connection() as conn:
                    import aiomysql
                    async with conn.cursor(aiomysql.DictCursor) as cursor:
                        sql = "SELECT t.id FROM meta_tables t JOIN meta_datasets d ON t.dataset_id = d.id WHERE d.data_source = %s AND t.physical_name = %s LIMIT 1"
                        await cursor.execute(sql, (datasource.source_name, table_name))
                        row = await cursor.fetchone()
                
                if row:
                    # 优先：使用精修元数据
                    full_table = await MetadataV2Service.get_table_by_id(row['id'])
                    if full_table:
                        results.append(MetadataYamlService.generate_table_yaml(full_table))
                else:
                    # 保底：抓取物理结构
                    adapter = await MetaService.get_adapter_by_id(source_id)
                    columns = await adapter.get_columns(table_name=table_name)
                    if columns:
                        col_lines = [f"    - {c['name']} ({c['type']})" + (f" # {c['comment']}" if c.get('comment') else "") for c in columns]
                        yaml = f"  - table: {table_name}\n    columns:\n" + "\n".join(col_lines)
                        results.append(yaml)
            except Exception as e:
                logger.error(f"Failed to fetch context for table {table_name}: {e}")
        
        return "DATABASE SCHEMA CONTEXT (RECOMMENDATION MODE):\n---\n" + "\n\n".join(results)

    @staticmethod
    async def get_schema_context(source_id: int, tables: Optional[List[str]] = None, prompt: Optional[str] = None) -> Dict[str, Any]:
        """Fetch a summary of tables and columns for AI context. Returns { 'context': str, 'recalled_items': [] }"""
        from app.services.metadata_v2_service import MetadataV2Service
        from app.services.metadata_yaml_service import MetadataYamlService
        from app.services.vector_service import VectorService
        from app.services.datasource_service import DataSourceService
        
        datasource = await DataSourceService.get_datasource(source_id)
        if not datasource: return {"context": "", "recalled_items": []}
        
        # 记录用户最初的手动勾选，用于后续精准归因
        user_selected_tables = list(tables) if (tables and len(tables) > 0) else []
        target_tables = list(user_selected_tables)
        recalled_items = []
        context_snippets = []
        
        # 1. Pure Semantic Recall
        if not target_tables and prompt:
            search_results = await VectorService.semantic_search(
                data_source=datasource.source_name, 
                query=prompt, 
                top_k=8,
                enable_rerank=True
            )
            for res in search_results:
                score = res.get('score', 0)
                # 移除 score < 0.05 的限制

                item_type = res.get('item_type')
                item_name = res.get('name')
                yaml_content = res.get('yaml_content', '')
                
                # 记录召回项
                recalled_items.append({
                    "type": item_type, 
                    "name": item_name, 
                    "reason": "语义匹配",
                    "score": score,
                    "debug_info": res.get('reasons')
                })
                
                # 直接将命中的 YAML 片段加入上下文
                if yaml_content:
                    context_snippets.append(yaml_content)
                
                # 如果是表类型且没有 yaml_content (罕见情况)，记录到 target_tables 走物理补全
                if item_type == 'table' and not yaml_content:
                    target_tables.append(item_name)

        # 2. Manual Selection & Fallback Logic (Only for items not covered by snippets)
        async def fetch_table_info(table_name: str) -> str:
            # 如果该表已经在语义结果里了，不再重复抓取
            if any(i['name'] == table_name and i['type'] == 'table' for i in recalled_items):
                return ""
            
            try:
                async with get_db_connection() as conn:
                    import aiomysql
                    async with conn.cursor(aiomysql.DictCursor) as cursor:
                        sql = "SELECT t.id FROM meta_tables t JOIN meta_datasets d ON t.dataset_id = d.id WHERE d.data_source = %s AND t.physical_name = %s LIMIT 1"
                        await cursor.execute(sql, (datasource.source_name, table_name))
                        row = await cursor.fetchone()
                if row:
                    full_table = await MetadataV2Service.get_table_by_id(row['id'])
                    if full_table:
                        recalled_items.append({"type": "table", "name": table_name, "reason": "手动勾选"})
                        return MetadataYamlService.generate_table_yaml(full_table)
                
                # Fallback to physical adapter
                adapter = await MetaService.get_adapter_by_id(source_id)
                columns = await adapter.get_columns(table_name=table_name)
                recalled_items.append({"type": "table", "name": table_name, "reason": "物理补全"})
                col_lines = [f"    - {c['name']} ({c['type']})" + (f" # {c['comment']}" if c.get('comment') else "") for c in columns]
                return f"  - table: {table_name}\n    columns:\n" + "\n".join(col_lines)
            except: return ""

        if target_tables:
            manual_results = await asyncio.gather(*[fetch_table_info(t) for t in target_tables])
            context_snippets.extend([r for r in manual_results if r])

        if not context_snippets: return {"context": "No schema context available.", "recalled_items": []}

        return {
            "context": "DATABASE SCHEMA CONTEXT (YAML):\n---\n" + "\n\n".join(context_snippets),
            "recalled_items": recalled_items
        }

    @classmethod
    async def check_resource_access(cls, user_id: int, resource_key: str) -> bool:
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT 1 FROM sys_user_resources WHERE user_id = %s AND resource_key = %s LIMIT 1", (user_id, resource_key))
                if await cursor.fetchone(): return True
                await cursor.execute("SELECT role_id FROM sys_user_role_relation WHERE user_id = %s", (user_id,))
                role_ids = [r[0] for r in await cursor.fetchall()]
                if role_ids:
                    placeholders = ', '.join(['%s'] * len(role_ids))
                    await cursor.execute(f"SELECT 1 FROM sys_ui_permissions WHERE enabled = 1 AND perm_type = 'resource' AND perm_code = %s AND role_id IN ({placeholders}) LIMIT 1", (resource_key, *role_ids))
                    if await cursor.fetchone(): return True
                return False