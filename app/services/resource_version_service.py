import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import get_db_connection
from app.schemas.resource import ResourceResponse
from app.schemas.resource_version import (
    ResourceVersionDetail,
    ResourceVersionDiffItem,
    ResourceVersionDiffResponse,
    ResourceVersionListResponse,
    ResourceVersionSummary,
)

logger = logging.getLogger(__name__)

SNAPSHOT_FIELDS = (
    "resource_key",
    "resource_name",
    "resource_group",
    "data_source",
    "resource_mode",
    "table_name",
    "custom_sql",
    "fields_config",
    "allowed_filters",
    "default_sort",
    "status",
    "cache_ttl",
    "remarks",
)

FIELD_LABELS = {
    "resource_name": "资源名称",
    "resource_group": "分组",
    "data_source": "数据源",
    "resource_mode": "模式",
    "table_name": "物理表",
    "custom_sql": "自定义 SQL",
    "fields_config": "返回字段",
    "allowed_filters": "过滤字段",
    "default_sort": "默认排序",
    "status": "状态",
    "cache_ttl": "缓存 TTL",
    "remarks": "备注",
}

MAX_VERSIONS_PER_RESOURCE = 100


class ResourceVersionService:
    @staticmethod
    def snapshot_from_resource(resource: ResourceResponse) -> Dict[str, Any]:
        data = resource.dict()
        return {field: data.get(field) for field in SNAPSHOT_FIELDS}

    @staticmethod
    def _normalize_json_value(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value

    @classmethod
    def _values_differ(cls, field: str, left: Any, right: Any) -> bool:
        left_val = cls._normalize_json_value(left)
        right_val = cls._normalize_json_value(right)
        if field in ("fields_config", "allowed_filters"):
            return json.dumps(left_val, sort_keys=True, ensure_ascii=False) != json.dumps(
                right_val, sort_keys=True, ensure_ascii=False
            )
        return left_val != right_val

    @classmethod
    def compute_change_summary(
        cls, before: ResourceResponse, after: Dict[str, Any]
    ) -> Optional[str]:
        changed: List[str] = []
        before_data = before.dict()
        for field in SNAPSHOT_FIELDS:
            if field == "resource_key":
                continue
            if field not in after:
                continue
            if cls._values_differ(field, before_data.get(field), after.get(field)):
                changed.append(FIELD_LABELS.get(field, field))
        return "、".join(changed) if changed else None

    @classmethod
    async def record_version(
        cls,
        resource: ResourceResponse,
        action_type: str,
        operator: Optional[Dict[str, Any]] = None,
        change_summary: Optional[str] = None,
    ) -> Optional[int]:
        snapshot = cls.snapshot_from_resource(resource)
        operator_user_id = int(operator["user_id"]) if operator and operator.get("user_id") else None
        operator_name = operator.get("user_name") if operator else None

        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT COALESCE(MAX(version_no), 0) FROM sys_resource_meta_versions WHERE resource_key = %s",
                    (resource.resource_key,),
                )
                row = await cursor.fetchone()
                next_version = int(row[0]) + 1

                await cursor.execute(
                    """
                    INSERT INTO sys_resource_meta_versions
                    (resource_key, version_no, action_type, snapshot, change_summary, operator_user_id, operator_name)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        resource.resource_key,
                        next_version,
                        action_type,
                        json.dumps(snapshot, ensure_ascii=False),
                        change_summary,
                        operator_user_id,
                        operator_name,
                    ),
                )
                version_id = cursor.lastrowid

                await cursor.execute(
                    """
                    SELECT id FROM sys_resource_meta_versions
                    WHERE resource_key = %s
                    ORDER BY version_no DESC
                    LIMIT 100 OFFSET %s
                    """,
                    (resource.resource_key, MAX_VERSIONS_PER_RESOURCE),
                )
                stale_ids = [r[0] for r in await cursor.fetchall()]
                if stale_ids:
                    placeholders = ", ".join(["%s"] * len(stale_ids))
                    await cursor.execute(
                        f"DELETE FROM sys_resource_meta_versions WHERE id IN ({placeholders})",
                        tuple(stale_ids),
                    )

                await conn.commit()
                return version_id

    @staticmethod
    def _map_summary_row(row: tuple) -> ResourceVersionSummary:
        return ResourceVersionSummary(
            id=row[0],
            resource_key=row[1],
            version_no=row[2],
            action_type=row[3],
            change_summary=row[4],
            operator_user_id=row[5],
            operator_name=row[6],
            created_at=row[7],
        )

    @classmethod
    async def list_versions(
        cls, resource_key: str, page: int = 1, size: int = 20
    ) -> ResourceVersionListResponse:
        page = max(page, 1)
        size = min(max(size, 1), 100)
        offset = (page - 1) * size

        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT COUNT(*) FROM sys_resource_meta_versions WHERE resource_key = %s",
                    (resource_key,),
                )
                total = int((await cursor.fetchone())[0])

                await cursor.execute(
                    """
                    SELECT id, resource_key, version_no, action_type, change_summary,
                           operator_user_id, operator_name, created_at
                    FROM sys_resource_meta_versions
                    WHERE resource_key = %s
                    ORDER BY version_no DESC
                    LIMIT %s OFFSET %s
                    """,
                    (resource_key, size, offset),
                )
                items = [cls._map_summary_row(row) for row in await cursor.fetchall()]

        return ResourceVersionListResponse(total=total, items=items)

    @classmethod
    async def list_recent_for_keys(
        cls, resource_keys: List[str], per_key_limit: int = 5
    ) -> Dict[str, ResourceVersionListResponse]:
        keys = [k for k in dict.fromkeys(resource_keys) if k]
        if not keys:
            return {}

        per_key_limit = min(max(per_key_limit, 1), 20)
        placeholders = ", ".join(["%s"] * len(keys))
        result: Dict[str, ResourceVersionListResponse] = {
            key: ResourceVersionListResponse(total=0, items=[]) for key in keys
        }

        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    f"""
                    SELECT resource_key, COUNT(*) FROM sys_resource_meta_versions
                    WHERE resource_key IN ({placeholders})
                    GROUP BY resource_key
                    """,
                    tuple(keys),
                )
                for resource_key, total in await cursor.fetchall():
                    if resource_key in result:
                        result[resource_key].total = int(total)

                await cursor.execute(
                    f"""
                    SELECT id, resource_key, version_no, action_type, change_summary,
                           operator_user_id, operator_name, created_at
                    FROM (
                        SELECT id, resource_key, version_no, action_type, change_summary,
                               operator_user_id, operator_name, created_at,
                               ROW_NUMBER() OVER (
                                   PARTITION BY resource_key ORDER BY version_no DESC
                               ) AS rn
                        FROM sys_resource_meta_versions
                        WHERE resource_key IN ({placeholders})
                    ) ranked
                    WHERE rn <= %s
                    ORDER BY resource_key, version_no DESC
                    """,
                    tuple(keys) + (per_key_limit,),
                )
                for row in await cursor.fetchall():
                    summary = cls._map_summary_row(row[:8])
                    bucket = result.get(summary.resource_key)
                    if bucket:
                        bucket.items.append(summary)

        return result

    @classmethod
    async def get_version(cls, version_id: int) -> Optional[ResourceVersionDetail]:
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT id, resource_key, version_no, action_type, change_summary,
                           operator_user_id, operator_name, created_at, snapshot
                    FROM sys_resource_meta_versions
                    WHERE id = %s
                    """,
                    (version_id,),
                )
                row = await cursor.fetchone()
                if not row:
                    return None

                snapshot = row[8]
                if isinstance(snapshot, str):
                    snapshot = json.loads(snapshot)

                summary = cls._map_summary_row(row[:8])
                return ResourceVersionDetail(**summary.dict(), snapshot=snapshot)

    @classmethod
    async def _get_adjacent_version(
        cls, resource_key: str, version_no: int
    ) -> Optional[Dict[str, Any]]:
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT snapshot FROM sys_resource_meta_versions
                    WHERE resource_key = %s AND version_no = %s
                    LIMIT 1
                    """,
                    (resource_key, version_no - 1),
                )
                row = await cursor.fetchone()
                if not row:
                    return None
                snapshot = row[0]
                if isinstance(snapshot, str):
                    snapshot = json.loads(snapshot)
                return snapshot

    @classmethod
    def build_diff(
        cls,
        resource_key: str,
        version_id: int,
        version_no: int,
        left: Dict[str, Any],
        right: Dict[str, Any],
        compare_target: str,
    ) -> ResourceVersionDiffResponse:
        items: List[ResourceVersionDiffItem] = []
        for field in SNAPSHOT_FIELDS:
            if field == "resource_key":
                continue
            left_val = left.get(field)
            right_val = right.get(field)
            if cls._values_differ(field, left_val, right_val):
                items.append(
                    ResourceVersionDiffItem(
                        field=field,
                        label=FIELD_LABELS.get(field, field),
                        current_value=left_val,
                        version_value=right_val,
                    )
                )

        return ResourceVersionDiffResponse(
            resource_key=resource_key,
            version_id=version_id,
            version_no=version_no,
            compare_target=compare_target,
            items=items,
        )

    @classmethod
    async def diff_version(
        cls,
        resource_key: str,
        version_id: int,
        current: ResourceResponse,
        compare_target: str = "current",
    ) -> Optional[ResourceVersionDiffResponse]:
        version = await cls.get_version(version_id)
        if not version or version.resource_key != resource_key:
            return None

        current_snapshot = cls.snapshot_from_resource(current)
        if compare_target == "previous":
            previous = await cls._get_adjacent_version(resource_key, version.version_no)
            if not previous:
                return cls.build_diff(
                    resource_key,
                    version_id,
                    version.version_no,
                    version.snapshot,
                    current_snapshot,
                    compare_target,
                )
            return cls.build_diff(
                resource_key,
                version_id,
                version.version_no,
                previous,
                version.snapshot,
                compare_target,
            )

        return cls.build_diff(
            resource_key,
            version_id,
            version.version_no,
            current_snapshot,
            version.snapshot,
            compare_target,
        )

    @classmethod
    async def get_snapshot_for_rollback(cls, version_id: int) -> Optional[Tuple[str, Dict[str, Any], int]]:
        version = await cls.get_version(version_id)
        if not version:
            return None
        return version.resource_key, version.snapshot, version.version_no
