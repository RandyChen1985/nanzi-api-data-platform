import json
import re
import csv
import io
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Set, Union

import aiomysql

from app.core.database import get_db_connection
from app.services.meta_service import MetaService
from app.services.permission_service import PermissionService
from app.services.resource_version_service import ResourceVersionService
from app.schemas.resource_version import ResourceVersionListResponse

logger = logging.getLogger(__name__)

STATUS_DRAFT = 0
STATUS_PUBLISHED = 1
STATUS_OFFLINE = 2

REQUEST_PENDING = 0
REQUEST_APPROVED = 1
REQUEST_REJECTED = 2
REQUEST_REVOKED = 3

RESOURCE_ENDPOINT_RE = re.compile(r"^/api/v1/resources/([^/?]+)")

RESOURCE_KEY_JOIN_SQL = "m.resource_key = pr.resource_key"


class CatalogService:
    @staticmethod
    def _parse_tags(raw: Any) -> List[str]:
        if raw is None:
            return []
        if isinstance(raw, list):
            return [str(t) for t in raw]
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                return parsed if isinstance(parsed, list) else []
            except json.JSONDecodeError:
                return []
        return []

    @staticmethod
    async def _get_resource_call_stats(days: int = 7) -> Dict[str, int]:
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        stats: Dict[str, int] = {}
        async with get_db_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    """
                    SELECT endpoint, SUM(total_calls) AS total
                    FROM api_access_stats_1m
                    WHERE time_bucket >= %s
                      AND user_name != 'ALL'
                      AND endpoint LIKE '/api/v1/resources/%%'
                    GROUP BY endpoint
                    """,
                    (since,),
                )
                for row in await cursor.fetchall():
                    match = RESOURCE_ENDPOINT_RE.match(row["endpoint"] or "")
                    if match:
                        key = match.group(1)
                        stats[key] = stats.get(key, 0) + int(row["total"] or 0)
        return stats

    @staticmethod
    async def _get_calls_trend(days: int = 7, resource_keys: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        since = (datetime.now() - timedelta(days=days - 1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        since_str = since.strftime("%Y-%m-%d %H:%M:%S")
        patterns = [f"/api/v1/resources/{k}" for k in (resource_keys or [])]
        async with get_db_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                if patterns:
                    placeholders = ", ".join(["%s"] * len(patterns))
                    sql = f"""
                        SELECT DATE(time_bucket) AS day_key, SUM(total_calls) AS total
                        FROM api_access_stats_1m
                        WHERE time_bucket >= %s AND user_name != 'ALL'
                          AND endpoint IN ({placeholders})
                        GROUP BY day_key ORDER BY day_key
                    """
                    await cursor.execute(sql, (since_str, *patterns))
                else:
                    await cursor.execute(
                        """
                        SELECT DATE(time_bucket) AS day_key, SUM(total_calls) AS total
                        FROM api_access_stats_1m
                        WHERE time_bucket >= %s AND user_name = 'ALL' AND endpoint = 'ALL'
                        GROUP BY day_key ORDER BY day_key
                        """,
                        (since_str,),
                    )
                rows = await cursor.fetchall()
        return [
            {"date": r["day_key"].strftime("%Y-%m-%d") if r["day_key"] else "", "calls": int(r["total"] or 0)}
            for r in rows
        ]

    @classmethod
    async def _user_resource_keys(cls, user: Dict) -> Set[str]:
        if user.get("role") == "admin":
            resources = await MetaService.list_resources()
            return {r.resource_key for r in resources}
        perms = await PermissionService.get_user_permissions(int(user["user_id"]))
        return set(perms.permissions.resources)

    @classmethod
    def _product_has_access(cls, resource_keys: List[str], accessible: Set[str]) -> bool:
        keys = [k for k in resource_keys if k]
        if not keys:
            return False
        return all(k in accessible for k in keys)

    @classmethod
    async def _get_resource_keys_by_product_ids(cls, product_ids: List[int]) -> Dict[int, List[str]]:
        if not product_ids:
            return {}
        placeholders = ", ".join(["%s"] * len(product_ids))
        sql = f"""
            SELECT product_id, resource_key
            FROM data_product_resources
            WHERE product_id IN ({placeholders})
            ORDER BY is_primary DESC, sort_order
        """
        result: Dict[int, List[str]] = {}
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql, tuple(product_ids))
                for product_id, resource_key in await cursor.fetchall():
                    if resource_key:
                        result.setdefault(int(product_id), []).append(resource_key)
        return result

    @classmethod
    async def _get_catalog_owner_config(cls) -> Dict[str, Any]:
        strategy = "publisher"
        group_map: Dict[str, int] = {}
        async with get_db_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    """
                    SELECT config_key, config_value FROM sys_config
                    WHERE config_key IN ('catalog.default_owner_strategy', 'catalog.group_owner_map')
                    """
                )
                for row in await cursor.fetchall():
                    if row["config_key"] == "catalog.default_owner_strategy":
                        strategy = (row["config_value"] or "publisher").strip()
                    elif row["config_key"] == "catalog.group_owner_map":
                        try:
                            raw = json.loads(row["config_value"] or "{}")
                            if isinstance(raw, dict):
                                group_map = {str(k): int(v) for k, v in raw.items()}
                        except (json.JSONDecodeError, TypeError, ValueError):
                            group_map = {}
        return {"strategy": strategy, "group_map": group_map}

    @classmethod
    async def get_catalog_settings(cls) -> Dict[str, Any]:
        cfg = await cls._get_catalog_owner_config()
        return {
            "default_owner_strategy": cfg["strategy"],
            "group_owner_map": cfg["group_map"],
        }

    @classmethod
    async def update_catalog_settings(
        cls,
        *,
        default_owner_strategy: str,
        group_owner_map: Dict[str, int],
    ) -> None:
        strategy = (default_owner_strategy or "publisher").strip()
        if strategy not in ("publisher", "group_owner", "none"):
            raise ValueError("default_owner_strategy 须为 publisher / group_owner / none")
        user_ids = list({int(v) for v in group_owner_map.values()})
        if user_ids:
            placeholders = ", ".join(["%s"] * len(user_ids))
            async with get_db_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        f"SELECT COUNT(*) FROM api_users WHERE id IN ({placeholders}) AND status = 1",
                        tuple(user_ids),
                    )
                    row = await cursor.fetchone()
                    if int(row[0] or 0) != len(user_ids):
                        raise ValueError("分组负责人映射中存在无效或已禁用的用户")
        map_json = json.dumps(group_owner_map, ensure_ascii=False)
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE sys_config SET config_value = %s WHERE config_key = %s",
                    (strategy, "catalog.default_owner_strategy"),
                )
                await cursor.execute(
                    "UPDATE sys_config SET config_value = %s WHERE config_key = %s",
                    (map_json, "catalog.group_owner_map"),
                )
                await conn.commit()

    @classmethod
    async def _resolve_default_owner(cls, user: Dict, resource_group: str) -> Optional[int]:
        cfg = await cls._get_catalog_owner_config()
        strategy = cfg["strategy"]
        if strategy == "none":
            return None
        if strategy == "group_owner":
            uid = cfg["group_map"].get(resource_group or "")
            if uid:
                return uid
        return int(user["user_id"])

    @classmethod
    def _featured_bool(cls, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        try:
            return int(value) == 1
        except (TypeError, ValueError):
            return bool(value)

    @classmethod
    def _row_to_list_item(
        cls,
        row: Dict[str, Any],
        call_stats: Dict[str, int],
        accessible: Set[str],
        resource_keys: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        resource_key = row.get("primary_resource_key") or row.get("product_key")
        tags = cls._parse_tags(row.get("tags"))
        if row.get("data_source") and row["data_source"] not in tags:
            tags = list(dict.fromkeys(tags + [row["data_source"]]))
        keys_for_access = resource_keys if resource_keys is not None else ([resource_key] if resource_key else [])
        keys_for_calls = keys_for_access
        calls = sum(call_stats.get(k, 0) for k in keys_for_calls)
        return {
            "id": row["id"],
            "product_key": row["product_key"],
            "display_name": row["display_name"],
            "summary": row.get("summary"),
            "domain": row.get("domain") or "默认域",
            "tags": tags,
            "status": row.get("status", 0),
            "featured": cls._featured_bool(row.get("featured")),
            "owner_name": row.get("owner_name"),
            "owner_user_id": row.get("owner_user_id"),
            "primary_resource_key": resource_key,
            "resource_group": row.get("resource_group"),
            "data_source": row.get("data_source"),
            "resource_mode": row.get("resource_mode"),
            "health_score": row.get("health_score"),
            "calls_7d": calls,
            "has_access": cls._product_has_access(keys_for_access, accessible),
            "published_at": row.get("published_at"),
            "updated_at": row.get("updated_at"),
        }

    @classmethod
    async def _fetch_product_rows(
        cls,
        *,
        product_key: Optional[str] = None,
        domain: Optional[str] = None,
        q: Optional[str] = None,
        status: Optional[int] = STATUS_PUBLISHED,
        featured_only: bool = False,
        owner_user_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        conditions = ["1=1"]
        params: List[Any] = []
        if product_key:
            conditions.append("p.product_key = %s")
            params.append(product_key)
        if domain:
            conditions.append("p.domain = %s")
            params.append(domain)
        if owner_user_id is not None:
            conditions.append("p.owner_user_id = %s")
            params.append(owner_user_id)
        if status is not None:
            conditions.append("p.status = %s")
            params.append(status)
        if featured_only:
            conditions.append("p.featured = 1")
        if q:
            conditions.append(
                "(p.display_name LIKE %s OR p.summary LIKE %s OR p.product_key LIKE %s OR p.domain LIKE %s)"
            )
            like = f"%{q}%"
            params.extend([like, like, like, like])

        limit_sql = f" LIMIT {int(limit)}" if limit else ""
        sql = f"""
            SELECT
                p.*,
                u.user_name AS owner_name,
                pr.resource_key AS primary_resource_key,
                m.resource_mode,
                m.resource_group,
                m.data_source,
                d.health_score,
                d.display_name AS dataset_name
            FROM data_products p
            LEFT JOIN api_users u ON u.id = p.owner_user_id
            LEFT JOIN data_product_resources pr ON pr.product_id = p.id AND pr.is_primary = 1
            LEFT JOIN sys_resource_meta m ON {RESOURCE_KEY_JOIN_SQL}
            LEFT JOIN meta_datasets d ON d.id = p.dataset_id
            WHERE {' AND '.join(conditions)}
            ORDER BY p.featured DESC, p.published_at DESC, p.updated_at DESC
            {limit_sql}
        """
        async with get_db_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql, tuple(params))
                return await cursor.fetchall()

    @classmethod
    async def _get_pending_counts_by_product(cls, product_keys: Optional[List[str]] = None) -> Dict[str, int]:
        conditions = ["status = %s"]
        params: List[Any] = [REQUEST_PENDING]
        if product_keys:
            placeholders = ", ".join(["%s"] * len(product_keys))
            conditions.append(f"product_key IN ({placeholders})")
            params.extend(product_keys)
        sql = f"""
            SELECT product_key, COUNT(*) AS cnt
            FROM data_product_access_requests
            WHERE {' AND '.join(conditions)}
            GROUP BY product_key
        """
        async with get_db_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql, tuple(params))
                rows = await cursor.fetchall()
        return {r["product_key"]: int(r["cnt"]) for r in rows}

    @classmethod
    async def list_products(
        cls,
        user: Dict,
        *,
        domain: Optional[str] = None,
        q: Optional[str] = None,
        sort: str = "calls",
        only_accessible: bool = False,
        only_no_access: bool = False,
        mine_only: bool = False,
        include_draft: bool = False,
        page: Optional[int] = None,
        page_size: int = 24,
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        admin = user.get("role") == "admin"
        user_id = int(user["user_id"])

        if mine_only:
            status = None
            owner_filter = user_id
        elif admin and include_draft:
            status = None
            owner_filter = None
        else:
            status = STATUS_PUBLISHED
            owner_filter = None

        rows = await cls._fetch_product_rows(
            domain=domain, q=q, status=status, owner_user_id=owner_filter
        )
        call_stats = await cls._get_resource_call_stats(7)
        accessible = await cls._user_resource_keys(user)

        pending_map: Dict[str, int] = {}
        if mine_only:
            keys = [r["product_key"] for r in rows]
            if keys:
                pending_map = await cls._get_pending_counts_by_product(keys)

        keys_map = await cls._get_resource_keys_by_product_ids([r["id"] for r in rows])

        items = []
        for r in rows:
            rkeys = keys_map.get(r["id"])
            if not rkeys:
                fallback = r.get("primary_resource_key") or r.get("product_key")
                rkeys = [fallback] if fallback else []
            item = cls._row_to_list_item(r, call_stats, accessible, resource_keys=rkeys)
            if mine_only:
                item["pending_requests"] = pending_map.get(r["product_key"], 0)
            items.append(item)

        if only_accessible:
            items = [i for i in items if i["has_access"]]
        elif only_no_access:
            items = [i for i in items if not i["has_access"]]

        if sort == "calls":
            items.sort(key=lambda x: x["calls_7d"], reverse=True)
        elif sort == "newest":
            items.sort(key=lambda x: x.get("published_at") or x.get("updated_at") or "", reverse=True)
        elif sort == "pending":
            items.sort(key=lambda x: x.get("pending_requests", 0), reverse=True)
        else:
            items.sort(key=lambda x: x["display_name"])

        if page is not None:
            total = len(items)
            start = (page - 1) * page_size
            return {
                "items": items[start : start + page_size],
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        return items

    @classmethod
    async def get_mine_summary(cls, user: Dict) -> Dict[str, int]:
        user_id = int(user["user_id"])
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT COUNT(*) FROM data_products WHERE owner_user_id = %s",
                    (user_id,),
                )
                owned = int((await cursor.fetchone())[0])
        pending = await cls.count_pending_requests(user)
        return {"owned_products": owned, "pending_review": pending}

    @classmethod
    def can_access_catalog_requests(cls, user: Dict, *, owned_products: int = 0) -> bool:
        """是否可进入目录权限申请页（审批/查看待办）"""
        if user.get("role") == "admin":
            return True
        perms = user.get("permissions", {}).get("elements", [])
        menus = user.get("permissions", {}).get("menus", [])
        if "menu:catalog:requests" in menus:
            return True
        if "element:catalog:review" in perms:
            return True
        if owned_products > 0:
            return True
        return False

    @classmethod
    async def export_products_csv(cls, user: Dict) -> str:
        products = await cls.list_products(user, sort="calls")
        output = io.StringIO()
        output.write("\ufeff")
        writer = csv.writer(output)
        writer.writerow([
            "产品Key", "展示名称", "业务域", "负责人", "数据源", "模式",
            "7日调用量", "健康分", "状态", "上架时间",
        ])
        status_labels = {0: "草稿", 1: "已发布", 2: "已下线"}
        for p in products:
            pub = p.get("published_at")
            if pub and hasattr(pub, "strftime"):
                pub = pub.strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow([
                p.get("product_key"),
                p.get("display_name"),
                p.get("domain"),
                p.get("owner_name") or "",
                p.get("data_source") or "",
                p.get("resource_mode") or "",
                p.get("calls_7d", 0),
                p.get("health_score") if p.get("health_score") is not None else "",
                status_labels.get(p.get("status", 1), ""),
                pub or "",
            ])
        return output.getvalue()

    @classmethod
    async def get_product(cls, product_key: str, user: Dict) -> Optional[Dict[str, Any]]:
        admin = user.get("role") == "admin"
        can_edit = await cls.can_edit_product(user, product_key)
        row_list = await cls._fetch_product_rows(
            product_key=product_key,
            status=None if (admin or can_edit) else STATUS_PUBLISHED,
            limit=1,
        )
        if not row_list:
            return None
        row = row_list[0]
        call_stats = await cls._get_resource_call_stats(7)
        accessible = await cls._user_resource_keys(user)
        item = cls._row_to_list_item(row, call_stats, accessible)

        resource_keys: List[str] = []
        async with get_db_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    f"""
                    SELECT pr.resource_key, pr.is_primary, m.resource_name, m.resource_mode,
                           m.resource_group, m.data_source, m.fields_config, m.allowed_filters
                    FROM data_product_resources pr
                    JOIN sys_resource_meta m ON {RESOURCE_KEY_JOIN_SQL}
                    WHERE pr.product_id = %s
                    ORDER BY pr.sort_order, pr.is_primary DESC
                    """,
                    (row["id"],),
                )
                resource_rows = await cursor.fetchall()

        resources = []
        for rr in resource_rows:
            resource_keys.append(rr["resource_key"])
            fc = rr.get("fields_config")
            af = rr.get("allowed_filters")
            if isinstance(fc, str):
                fc = json.loads(fc)
            if isinstance(af, str):
                af = json.loads(af)
            resources.append(
                {
                    "resource_key": rr["resource_key"],
                    "resource_name": rr.get("resource_name"),
                    "resource_mode": rr.get("resource_mode"),
                    "resource_group": rr.get("resource_group"),
                    "data_source": rr.get("data_source"),
                    "fields_config": fc or [],
                    "allowed_filters": af or [],
                    "is_primary": bool(rr.get("is_primary")),
                }
            )

        item["has_access"] = cls._product_has_access(resource_keys, accessible)
        item["description"] = row.get("description")
        item["resources"] = resources
        item["dataset_name"] = row.get("dataset_name")
        item["dataset_id"] = row.get("dataset_id")
        item["calls_trend"] = await cls._get_calls_trend(7, resource_keys)
        item["can_edit"] = await cls.can_edit_product(user, product_key)
        item["can_manage_access"] = await cls.can_revoke_access(user, product_key)
        if not item["has_access"] and row.get("status") == STATUS_PUBLISHED:
            req_status = await cls.get_user_request_status(int(user["user_id"]), product_key)
            item["access_request_status"] = req_status
        else:
            item["access_request_status"] = None
        return item

    @classmethod
    async def list_domains(cls, user: Dict) -> List[Dict[str, Any]]:
        products = await cls.list_products(user, sort="name")
        counts: Dict[str, int] = {}
        for p in products:
            counts[p["domain"]] = counts.get(p["domain"], 0) + 1
        return [{"domain": d, "count": c} for d, c in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]

    @classmethod
    async def get_sections(cls, user: Dict) -> Dict[str, List[Dict[str, Any]]]:
        products = await cls.list_products(user, sort="calls")
        hot = sorted(products, key=lambda x: x["calls_7d"], reverse=True)[:6]
        newest = sorted(
            products,
            key=lambda x: x.get("published_at") or x.get("updated_at") or "",
            reverse=True,
        )[:6]
        featured = [p for p in products if p.get("featured")]
        return {"hot": hot, "newest": newest, "featured": featured}

    @classmethod
    async def upsert_from_resource(
        cls,
        resource_key: str,
        *,
        user: Optional[Dict] = None,
        display_name: Optional[str] = None,
        summary: Optional[str] = None,
        domain: Optional[str] = None,
        owner_user_id: Optional[int] = None,
        publish: bool = False,
    ) -> Dict[str, Any]:
        config = await MetaService.get_config(resource_key)
        if not config:
            raise ValueError(f"资源 {resource_key} 不存在")
        if config.resource_group.strip().lower() == "system":
            raise ValueError("系统内置资源不可发布到目录")

        disp = display_name or config.resource_name
        summ = summary or (config.remarks or f"{config.resource_name} 数据 API")
        dom = domain or config.resource_group or "默认域"
        tags = json.dumps([config.data_source], ensure_ascii=False)
        status = STATUS_PUBLISHED if publish else STATUS_DRAFT
        published_at = datetime.now() if publish else None

        if owner_user_id is None and user:
            owner_user_id = await cls._resolve_default_owner(user, config.resource_group or "")

        if publish:
            cls._validate_publishable_row({
                "display_name": disp,
                "summary": summ,
                "owner_user_id": owner_user_id,
            })

        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT id, status FROM data_products WHERE product_key = %s", (resource_key,))
                existing = await cursor.fetchone()
                if existing:
                    product_id, old_status = existing
                    new_status = status if publish else old_status
                    pub_at = published_at if publish else None
                    await cursor.execute(
                        """
                        UPDATE data_products
                        SET display_name=%s, summary=%s, domain=%s, tags=%s,
                            owner_user_id=COALESCE(%s, owner_user_id),
                            status=%s, published_at=COALESCE(%s, published_at)
                        WHERE id=%s
                        """,
                        (disp, summ, dom, tags, owner_user_id, new_status, pub_at, product_id),
                    )
                else:
                    await cursor.execute(
                        """
                        INSERT INTO data_products
                        (product_key, display_name, summary, domain, tags, owner_user_id, status, published_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (resource_key, disp, summ, dom, tags, owner_user_id, status, published_at),
                    )
                    product_id = cursor.lastrowid

                await cursor.execute(
                    """
                    INSERT INTO data_product_resources (product_id, resource_key, is_primary, sort_order)
                    VALUES (%s, %s, 1, 0)
                    ON DUPLICATE KEY UPDATE is_primary = VALUES(is_primary)
                    """,
                    (product_id, resource_key),
                )
                await conn.commit()

        return {"product_key": resource_key, "status": status, "published": publish}

    @classmethod
    async def publish_product(cls, product_key: str) -> bool:
        row = await cls._get_raw_product(product_key)
        if not row:
            return False
        cls._validate_publishable_row(row)
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE data_products
                    SET status=%s, published_at=COALESCE(published_at, NOW())
                    WHERE product_key=%s
                    """,
                    (STATUS_PUBLISHED, product_key),
                )
                await conn.commit()
                return cursor.rowcount > 0

    @classmethod
    async def unpublish_product(
        cls, product_key: str, *, revoke_permissions: bool = False
    ) -> bool:
        if revoke_permissions:
            await cls._revoke_all_product_access(product_key)
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE data_products SET status=%s WHERE product_key=%s",
                    (STATUS_OFFLINE, product_key),
                )
                await conn.commit()
                return cursor.rowcount > 0

    @classmethod
    async def update_product(cls, product_key: str, data: Dict[str, Any]) -> bool:
        fields = []
        params: List[Any] = []
        mapping = {
            "display_name": "display_name",
            "summary": "summary",
            "description": "description",
            "domain": "domain",
            "owner_user_id": "owner_user_id",
            "dataset_id": "dataset_id",
        }
        for key, col in mapping.items():
            if key in data and data[key] is not None:
                fields.append(f"{col}=%s")
                params.append(data[key])
        if "tags" in data and data["tags"] is not None:
            fields.append("tags=%s")
            params.append(json.dumps(data["tags"], ensure_ascii=False))
        if "featured" in data and data["featured"] is not None:
            fields.append("featured=%s")
            params.append(1 if data["featured"] else 0)
        if not fields:
            return False
        params.append(product_key)
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    f"UPDATE data_products SET {', '.join(fields)} WHERE product_key=%s",
                    tuple(params),
                )
                await conn.commit()
                return cursor.rowcount > 0

    @classmethod
    async def get_panorama(cls, days: int = 30) -> Dict[str, Any]:
        call_stats = await cls._get_resource_call_stats(days)
        rows = await cls._fetch_product_rows(status=STATUS_PUBLISHED)
        accessible: Set[str] = set()
        keys_map = await cls._get_resource_keys_by_product_ids([r["id"] for r in rows])
        catalog_resource_keys: Set[str] = set()

        products = []
        for r in rows:
            rkeys = keys_map.get(r["id"])
            if not rkeys:
                fallback = r.get("primary_resource_key") or r.get("product_key")
                rkeys = [fallback] if fallback else []
            catalog_resource_keys.update(rkeys)
            products.append(cls._row_to_list_item(r, call_stats, accessible, resource_keys=rkeys))

        total_calls = sum(p["calls_7d"] for p in products)

        domain_dist: Dict[str, int] = {}
        ds_types: Dict[str, int] = {}
        for p in products:
            domain_dist[p["domain"]] = domain_dist.get(p["domain"], 0) + 1
            ds = p.get("data_source") or "unknown"
            ds_types[ds] = ds_types.get(ds, 0) + 1

        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        active_consumers = 0
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT COUNT(DISTINCT user_name) FROM api_access_stats_1m
                    WHERE time_bucket >= %s AND user_name != 'ALL'
                    """,
                    (since,),
                )
                row = await cursor.fetchone()
                active_consumers = int(row[0] or 0) if row else 0

        health_summary = {"good": 0, "medium": 0, "low": 0, "unknown": 0}
        for p in products:
            score = p.get("health_score")
            if score is None:
                health_summary["unknown"] += 1
            elif score >= 80:
                health_summary["good"] += 1
            elif score >= 60:
                health_summary["medium"] += 1
            else:
                health_summary["low"] += 1

        zero_call = [p for p in products if p["calls_7d"] == 0]
        low_health = [p for p in products if p.get("health_score") is not None and p["health_score"] < 60]
        incomplete = [
            p for p in products
            if not (p.get("summary") or "").strip() or not p.get("owner_user_id")
        ]

        month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        new_month = sum(
            1 for p in products if p.get("published_at") and p["published_at"] >= month_start
        )

        top_products = sorted(products, key=lambda x: x["calls_7d"], reverse=True)[:10]
        calls_trend = await cls._get_calls_trend(
            days, sorted(catalog_resource_keys) if catalog_resource_keys else None
        )

        return {
            "period_days": days,
            "published_count": len(products),
            "domain_count": len(domain_dist),
            "datasource_types": ds_types,
            "total_calls": total_calls,
            "active_consumers": active_consumers,
            "domain_distribution": [{"domain": d, "count": c} for d, c in sorted(domain_dist.items(), key=lambda x: -x[1])],
            "calls_trend": calls_trend,
            "top_products": top_products,
            "health_summary": health_summary,
            "alerts": {
                "zero_call_products": zero_call[:10],
                "low_health_products": low_health[:10],
                "incomplete_products": incomplete[:10],
                "new_this_month": new_month,
            },
        }

    @classmethod
    async def get_product_status_map(cls) -> Dict[str, int]:
        async with get_db_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("SELECT product_key, status FROM data_products")
                rows = await cursor.fetchall()
        return {r["product_key"]: r["status"] for r in rows}

    @classmethod
    def _validate_publishable_row(cls, row: Dict[str, Any]) -> None:
        if not (row.get("display_name") or "").strip():
            raise ValueError("发布前须填写产品展示名称")
        if not (row.get("summary") or "").strip():
            raise ValueError("发布前须填写一句话简介")
        if not row.get("owner_user_id"):
            raise ValueError("发布前须指定产品负责人")

    @classmethod
    async def _get_raw_product(cls, product_key: str) -> Optional[Dict[str, Any]]:
        rows = await cls._fetch_product_rows(product_key=product_key, status=None, limit=1)
        return rows[0] if rows else None

    @classmethod
    async def can_edit_product(cls, user: Dict, product_key: str) -> bool:
        if user.get("role") == "admin":
            return True
        perms = user.get("permissions", {}).get("elements", [])
        if "element:catalog:manage" in perms:
            return True
        row = await cls._get_raw_product(product_key)
        if not row:
            return False
        return row.get("owner_user_id") == int(user["user_id"])

    @classmethod
    async def can_view_product(cls, user: Dict, product_key: str) -> bool:
        """已发布产品对所有登录用户可见；草稿/下线仅负责人或管理员可查看。"""
        row = await cls._get_raw_product(product_key)
        if not row:
            return False
        if user.get("role") == "admin":
            return True
        if await cls.can_edit_product(user, product_key):
            return True
        return row.get("status") == STATUS_PUBLISHED

    @classmethod
    async def can_review_requests(cls, user: Dict, product_key: Optional[str] = None) -> bool:
        if user.get("role") == "admin":
            return True
        perms = user.get("permissions", {}).get("elements", [])
        if "element:catalog:review" in perms:
            return True
        if product_key:
            row = await cls._get_raw_product(product_key)
            return bool(row and row.get("owner_user_id") == int(user["user_id"]))
        return False

    @classmethod
    async def get_edit_meta(cls, user: Dict, product_key: str) -> Dict[str, Any]:
        row = await cls._get_raw_product(product_key)
        if not row:
            raise ValueError("产品不存在")
        can_edit = await cls.can_edit_product(user, product_key)
        if not can_edit:
            raise PermissionError("无编辑权限")

        meta: Dict[str, Any] = {
            "can_edit": True,
            "is_admin": user.get("role") == "admin",
            "can_manage_catalog": user.get("role") == "admin"
            or "element:catalog:manage" in user.get("permissions", {}).get("elements", []),
            "featured": cls._featured_bool(row.get("featured")),
            "can_assign_owner": False,
            "domains": [],
            "users": [],
            "datasets": [],
        }
        domain_rows = await cls._fetch_product_rows(status=None)
        domains = sorted({r.get("domain") or "默认域" for r in domain_rows})
        meta["domains"] = domains

        perms = user.get("permissions", {}).get("elements", [])
        can_assign_owner = (
            user.get("role") == "admin"
            or "element:catalog:manage" in perms
            or row.get("owner_user_id") == int(user["user_id"])
        )
        meta["can_assign_owner"] = can_assign_owner

        if can_assign_owner:
            meta["users"] = await cls.list_active_users()
        if user.get("role") == "admin":
            async with get_db_connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(
                        "SELECT id, name, display_name, data_source FROM meta_datasets WHERE status = 1 ORDER BY display_name"
                    )
                    meta["datasets"] = await cursor.fetchall()
        resources_list = await MetaService.list_resources()
        meta["available_resources"] = [
            {
                "resource_key": r.resource_key,
                "resource_name": r.resource_name,
                "resource_group": r.resource_group,
                "resource_mode": r.resource_mode,
            }
            for r in resources_list
            if (r.resource_group or "").strip().lower() != "system"
        ]
        return meta

    @classmethod
    async def _product_linked_resource_meta(
        cls, product_id: int, resource_keys: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        async with get_db_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                if resource_keys:
                    placeholders = ", ".join(["%s"] * len(resource_keys))
                    await cursor.execute(
                        f"""
                        SELECT pr.resource_key, pr.is_primary, m.resource_name
                        FROM data_product_resources pr
                        LEFT JOIN sys_resource_meta m ON m.resource_key = pr.resource_key
                        WHERE pr.product_id = %s AND pr.resource_key IN ({placeholders})
                        ORDER BY pr.sort_order, pr.is_primary DESC
                        """,
                        (product_id, *resource_keys),
                    )
                else:
                    await cursor.execute(
                        """
                        SELECT pr.resource_key, pr.is_primary, m.resource_name
                        FROM data_product_resources pr
                        LEFT JOIN sys_resource_meta m ON m.resource_key = pr.resource_key
                        WHERE pr.product_id = %s
                        ORDER BY pr.sort_order, pr.is_primary DESC
                        """,
                        (product_id,),
                    )
                rows = await cursor.fetchall()

        meta: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            meta[row["resource_key"]] = {
                "resource_name": row.get("resource_name"),
                "is_primary": bool(row.get("is_primary")),
            }

        if resource_keys:
            return {k: meta[k] for k in resource_keys if k in meta}

        return meta

    @classmethod
    async def _enrich_unsaved_resource_keys(
        cls, product_id: int, resource_keys: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """编辑页预览：合并已保存关联与尚未保存的 resource_key。"""
        meta = await cls._product_linked_resource_meta(product_id, resource_keys)
        missing = [k for k in resource_keys if k not in meta]
        if missing:
            for resource in await MetaService.list_resources():
                if resource.resource_key in missing:
                    meta[resource.resource_key] = {
                        "resource_name": resource.resource_name,
                        "is_primary": False,
                    }
        return {k: meta.get(k, {"resource_name": None, "is_primary": False}) for k in resource_keys}

    @classmethod
    async def get_linked_resource_versions(
        cls,
        user: Dict,
        product_key: str,
        resource_keys: Optional[List[str]] = None,
        limit: int = 5,
    ) -> Dict[str, Any]:
        if not await cls.can_view_product(user, product_key):
            raise PermissionError("无权限查看该产品")
        row = await cls._get_raw_product(product_key)
        if not row:
            raise ValueError("产品不存在")

        can_edit = await cls.can_edit_product(user, product_key)
        if resource_keys:
            if can_edit:
                key_meta = await cls._enrich_unsaved_resource_keys(row["id"], resource_keys)
            else:
                db_meta = await cls._product_linked_resource_meta(row["id"])
                key_meta = {k: db_meta[k] for k in resource_keys if k in db_meta}
        else:
            key_meta = await cls._product_linked_resource_meta(row["id"])
        keys = list(key_meta.keys())
        if not keys:
            return {"product_key": product_key, "resources": []}

        version_map = await ResourceVersionService.list_recent_for_keys(keys, per_key_limit=limit)
        resources = []
        for key in keys:
            info = key_meta.get(key, {})
            versions = version_map.get(key) or ResourceVersionListResponse(total=0, items=[])
            resources.append(
                {
                    "resource_key": key,
                    "resource_name": info.get("resource_name"),
                    "is_primary": info.get("is_primary", False),
                    "total_versions": versions.total,
                    "recent_versions": [item.dict() for item in versions.items],
                }
            )
        return {"product_key": product_key, "resources": resources}

    @classmethod
    async def update_product_resources(
        cls,
        product_key: str,
        resources: List[Dict[str, Any]],
    ) -> bool:
        if not resources:
            raise ValueError("至少须关联一个 API 资源")
        primary_count = sum(1 for r in resources if r.get("is_primary"))
        if primary_count != 1:
            raise ValueError("须指定且仅能指定一个主资源")

        row = await cls._get_raw_product(product_key)
        if not row:
            raise ValueError("产品不存在")
        product_id = row["id"]

        keys = [str(r["resource_key"]).strip() for r in resources]
        if len(keys) != len(set(keys)):
            raise ValueError("资源列表存在重复项")

        for key in keys:
            config = await MetaService.get_config(key)
            if not config:
                raise ValueError(f"资源 {key} 不存在")
            if config.resource_group.strip().lower() == "system":
                raise ValueError(f"系统资源 {key} 不可关联到目录产品")

        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "DELETE FROM data_product_resources WHERE product_id = %s",
                    (product_id,),
                )
                for i, item in enumerate(resources):
                    await cursor.execute(
                        """
                        INSERT INTO data_product_resources
                        (product_id, resource_key, is_primary, sort_order)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            product_id,
                            item["resource_key"],
                            1 if item.get("is_primary") else 0,
                            i,
                        ),
                    )
                await conn.commit()
        return True

    @classmethod
    async def list_active_users(cls) -> List[Dict[str, Any]]:
        async with get_db_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, user_name, remark FROM api_users WHERE status = 1 ORDER BY user_name"
                )
                return await cursor.fetchall()

    @classmethod
    async def count_products_without_owner(cls) -> int:
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT COUNT(*) FROM data_products WHERE owner_user_id IS NULL"
                )
                row = await cursor.fetchone()
        return int(row[0] or 0) if row else 0

    @classmethod
    async def batch_assign_owner(
        cls,
        user: Dict,
        owner_user_id: int,
        *,
        product_keys: Optional[List[str]] = None,
        only_without_owner: bool = True,
    ) -> Dict[str, int]:
        if user.get("role") != "admin":
            perms = user.get("permissions", {}).get("elements", [])
            if "element:catalog:manage" not in perms:
                raise PermissionError("无权批量指定负责人")

        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT id FROM api_users WHERE id = %s AND status = 1",
                    (owner_user_id,),
                )
                if not await cursor.fetchone():
                    raise ValueError("负责人用户不存在或已禁用")

        if product_keys:
            keys = list(dict.fromkeys(product_keys))
        else:
            rows = await cls._fetch_product_rows(status=None)
            keys = [
                r["product_key"] for r in rows
                if not only_without_owner or not r.get("owner_user_id")
            ]

        updated = 0
        skipped = 0
        owner_clause = " AND owner_user_id IS NULL" if only_without_owner else ""
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                for key in keys:
                    await cursor.execute(
                        f"UPDATE data_products SET owner_user_id = %s WHERE product_key = %s{owner_clause}",
                        (owner_user_id, key),
                    )
                    if cursor.rowcount:
                        updated += 1
                    else:
                        skipped += 1
                await conn.commit()
        return {"updated": updated, "skipped": skipped, "total": len(keys)}

    @classmethod
    async def batch_publish_drafts(cls) -> Dict[str, Any]:
        rows = await cls._fetch_product_rows(status=STATUS_DRAFT)
        published = 0
        skipped: List[Dict[str, str]] = []
        for row in rows:
            key = row["product_key"]
            try:
                cls._validate_publishable_row(row)
                if await cls.publish_product(key):
                    published += 1
            except ValueError as e:
                skipped.append({
                    "product_key": key,
                    "display_name": row.get("display_name") or key,
                    "reason": str(e),
                })
        return {"published": published, "skipped": skipped, "total": len(rows)}

    @classmethod
    async def _get_product_resource_keys(cls, product_id: int) -> List[str]:
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT resource_key FROM data_product_resources WHERE product_id = %s ORDER BY is_primary DESC, sort_order",
                    (product_id,),
                )
                rows = await cursor.fetchall()
        return [r[0] for r in rows if r[0]]

    @classmethod
    async def _get_primary_resource_key(cls, product_id: int) -> Optional[str]:
        keys = await cls._get_product_resource_keys(product_id)
        return keys[0] if keys else None

    @classmethod
    async def get_user_request_status(cls, user_id: int, product_key: str) -> Optional[str]:
        async with get_db_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    """
                    SELECT status FROM data_product_access_requests
                    WHERE user_id = %s AND product_key = %s
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (user_id, product_key),
                )
                row = await cursor.fetchone()
                if not row:
                    return None
                if row["status"] == REQUEST_PENDING:
                    return "pending"
                if row["status"] == REQUEST_REJECTED:
                    return "rejected"
                if row["status"] == REQUEST_REVOKED:
                    return "revoked"
                return "approved"

    @classmethod
    async def create_access_request(cls, user: Dict, product_key: str, message: Optional[str] = None) -> Dict[str, Any]:
        product = await cls._get_raw_product(product_key)
        if not product or product.get("status") != STATUS_PUBLISHED:
            raise ValueError("产品不存在或未发布")
        user_id = int(user["user_id"])
        accessible = await cls._user_resource_keys(user)
        resource_keys = await cls._get_product_resource_keys(product["id"])
        if resource_keys and cls._product_has_access(resource_keys, accessible):
            raise ValueError("您已拥有该产品的访问权限")

        existing = await cls.get_user_request_status(user_id, product_key)
        if existing == "pending":
            raise ValueError("您已提交过申请，请等待审批")

        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO data_product_access_requests
                    (product_id, product_key, user_id, user_name, message, status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (product["id"], product_key, user_id, user["user_name"], message, REQUEST_PENDING),
                )
                await conn.commit()
                return {"id": cursor.lastrowid, "status": "pending"}

    @classmethod
    async def list_access_requests(
        cls, user: Dict, status: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        is_admin_user = user.get("role") == "admin"
        user_id = int(user["user_id"])

        conditions = ["1=1"]
        params: List[Any] = []
        if status is not None:
            conditions.append("r.status = %s")
            params.append(status)
        if not is_admin_user:
            perms = user.get("permissions", {}).get("elements", [])
            if "element:catalog:review" not in perms:
                conditions.append("(p.owner_user_id = %s OR r.user_id = %s)")
                params.extend([user_id, user_id])

        sql = f"""
            SELECT r.*, p.display_name AS product_name, p.owner_user_id
            FROM data_product_access_requests r
            JOIN data_products p ON p.id = r.product_id
            WHERE {' AND '.join(conditions)}
            ORDER BY r.created_at DESC
            LIMIT 200
        """
        async with get_db_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql, tuple(params))
                rows = await cursor.fetchall()
        for r in rows:
            if r.get("created_at"):
                r["created_at"] = r["created_at"].strftime("%Y-%m-%d %H:%M:%S")
            if r.get("handled_at"):
                r["handled_at"] = r["handled_at"].strftime("%Y-%m-%d %H:%M:%S")
            if r.get("updated_at"):
                r["updated_at"] = r["updated_at"].strftime("%Y-%m-%d %H:%M:%S")
            # 已通过但权限已被收回（含用户管理侧手动删权限）时补充展示字段
            if r.get("status") == REQUEST_APPROVED:
                r["access_active"] = await cls._user_has_product_resource_access(
                    int(r["user_id"]), int(r["product_id"])
                )
            else:
                r["access_active"] = False
        return rows

    @classmethod
    async def count_pending_requests(cls, user: Dict) -> int:
        is_admin_user = user.get("role") == "admin"
        user_id = int(user["user_id"])
        conditions = ["r.status = %s"]
        params: List[Any] = [REQUEST_PENDING]
        if not is_admin_user:
            perms = user.get("permissions", {}).get("elements", [])
            if "element:catalog:review" not in perms:
                # 产品负责人仅统计需本人审批的申请，不含自己作为申请人提交的
                conditions.append("p.owner_user_id = %s")
                params.append(user_id)
        sql = f"""
            SELECT COUNT(*) AS cnt
            FROM data_product_access_requests r
            JOIN data_products p ON p.id = r.product_id
            WHERE {' AND '.join(conditions)}
        """
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql, tuple(params))
                row = await cursor.fetchone()
        return int(row[0] or 0) if row else 0

    @classmethod
    async def count_access_requests_by_status(cls, user: Dict) -> Dict[str, int]:
        """按状态统计审批列表数量（与 list_access_requests 可见范围一致）"""
        is_admin_user = user.get("role") == "admin"
        user_id = int(user["user_id"])

        conditions = ["1=1"]
        params: List[Any] = []
        if not is_admin_user:
            perms = user.get("permissions", {}).get("elements", [])
            if "element:catalog:review" not in perms:
                conditions.append("(p.owner_user_id = %s OR r.user_id = %s)")
                params.extend([user_id, user_id])

        sql = f"""
            SELECT r.status, COUNT(*) AS cnt
            FROM data_product_access_requests r
            JOIN data_products p ON p.id = r.product_id
            WHERE {' AND '.join(conditions)}
            GROUP BY r.status
        """
        counts = {0: 0, 1: 0, 2: 0, 3: 0}
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql, tuple(params))
                rows = await cursor.fetchall()
        for row in rows:
            status = int(row[0])
            if status in counts:
                counts[status] = int(row[1] or 0)
        total = sum(counts.values())
        return {
            "0": counts[0],
            "1": counts[1],
            "2": counts[2],
            "3": counts[3],
            "all": total,
        }

    @classmethod
    async def approve_access_request(cls, request_id: int, handler: Dict, remark: Optional[str] = None) -> bool:
        async with get_db_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    """
                    SELECT r.*, p.owner_user_id FROM data_product_access_requests r
                    JOIN data_products p ON p.id = r.product_id
                    WHERE r.id = %s AND r.status = %s
                    """,
                    (request_id, REQUEST_PENDING),
                )
                req = await cursor.fetchone()
                if not req:
                    return False
                if handler.get("role") != "admin":
                    perms = handler.get("permissions", {}).get("elements", [])
                    if "element:catalog:review" not in perms and req["owner_user_id"] != int(handler["user_id"]):
                        raise PermissionError("无权审批该申请")

                resource_keys = await cls._get_product_resource_keys(req["product_id"])
                if not resource_keys:
                    raise ValueError("产品未关联 API 资源")

                for rk in resource_keys:
                    await cursor.execute(
                        "INSERT IGNORE INTO sys_user_resources (user_id, resource_key) VALUES (%s, %s)",
                        (req["user_id"], rk),
                    )
                await cursor.execute(
                    """
                    UPDATE data_product_access_requests
                    SET status=%s, handled_by=%s, handler_name=%s, handle_remark=%s, handled_at=NOW()
                    WHERE id=%s
                    """,
                    (REQUEST_APPROVED, int(handler["user_id"]), handler["user_name"], remark, request_id),
                )
                await conn.commit()

        await PermissionService.invalidate_user_cache(req["user_id"])
        return True

    @classmethod
    async def reject_access_request(cls, request_id: int, handler: Dict, remark: Optional[str] = None) -> bool:
        async with get_db_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    """
                    SELECT r.*, p.owner_user_id FROM data_product_access_requests r
                    JOIN data_products p ON p.id = r.product_id
                    WHERE r.id = %s AND r.status = %s
                    """,
                    (request_id, REQUEST_PENDING),
                )
                req = await cursor.fetchone()
                if not req:
                    return False
                if handler.get("role") != "admin":
                    perms = handler.get("permissions", {}).get("elements", [])
                    if "element:catalog:review" not in perms and req["owner_user_id"] != int(handler["user_id"]):
                        raise PermissionError("无权审批该申请")
                await cursor.execute(
                    """
                    UPDATE data_product_access_requests
                    SET status=%s, handled_by=%s, handler_name=%s, handle_remark=%s, handled_at=NOW()
                    WHERE id=%s
                    """,
                    (REQUEST_REJECTED, int(handler["user_id"]), handler["user_name"], remark, request_id),
                )
                await conn.commit()
        return True

    @classmethod
    async def can_revoke_access(cls, user: Dict, product_key: str) -> bool:
        if user.get("role") == "admin":
            return True
        perms = user.get("permissions", {}).get("elements", [])
        if "element:catalog:manage" in perms or "element:catalog:review" in perms:
            return True
        row = await cls._get_raw_product(product_key)
        return bool(row and row.get("owner_user_id") == int(user["user_id"]))

    @classmethod
    async def get_product_access_holders(cls, product_key: str) -> Dict[str, Any]:
        product = await cls._get_raw_product(product_key)
        if not product:
            raise ValueError("产品不存在")
        resource_keys = await cls._get_product_resource_keys(product["id"])
        if not resource_keys:
            return {"count": 0, "holders": []}
        placeholders = ", ".join(["%s"] * len(resource_keys))
        sql = f"""
            SELECT u.id AS user_id, u.user_name, u.remark,
                   COUNT(DISTINCT sur.resource_key) AS granted_resources
            FROM sys_user_resources sur
            JOIN api_users u ON u.id = sur.user_id
            WHERE sur.resource_key IN ({placeholders}) AND u.status = 1
            GROUP BY u.id, u.user_name, u.remark
            HAVING granted_resources > 0
            ORDER BY u.user_name
        """
        async with get_db_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql, tuple(resource_keys))
                rows = await cursor.fetchall()
        holders = [
            {
                "user_id": r["user_id"],
                "user_name": r["user_name"],
                "remark": r.get("remark"),
                "granted_resources": int(r["granted_resources"] or 0),
            }
            for r in rows
        ]
        return {"count": len(holders), "holders": holders}

    @classmethod
    async def _revoke_all_product_access(cls, product_key: str) -> int:
        product = await cls._get_raw_product(product_key)
        if not product:
            return 0
        resource_keys = await cls._get_product_resource_keys(product["id"])
        if not resource_keys:
            return 0
        return await cls._revoke_resources_for_users(resource_keys, user_ids=None)

    @classmethod
    async def _revoke_resources_for_users(
        cls,
        resource_keys: List[str],
        *,
        user_ids: Optional[List[int]] = None,
    ) -> int:
        if not resource_keys:
            return 0
        placeholders = ", ".join(["%s"] * len(resource_keys))
        params: List[Any] = list(resource_keys)
        user_clause = ""
        if user_ids:
            user_ph = ", ".join(["%s"] * len(user_ids))
            user_clause = f" AND user_id IN ({user_ph})"
            params.extend(user_ids)

        affected_users: Set[int] = set()
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    f"""
                    SELECT DISTINCT user_id FROM sys_user_resources
                    WHERE resource_key IN ({placeholders}){user_clause}
                    """,
                    tuple(params),
                )
                affected_users = {int(r[0]) for r in await cursor.fetchall()}
                await cursor.execute(
                    f"DELETE FROM sys_user_resources WHERE resource_key IN ({placeholders}){user_clause}",
                    tuple(params),
                )
                removed = cursor.rowcount
                await conn.commit()

        for uid in affected_users:
            await PermissionService.invalidate_user_cache(uid)
        return removed

    @classmethod
    async def _user_has_product_resource_access(cls, user_id: int, product_id: int) -> bool:
        resource_keys = await cls._get_product_resource_keys(product_id)
        if not resource_keys:
            return False
        placeholders = ", ".join(["%s"] * len(resource_keys))
        sql = f"""
            SELECT COUNT(*) FROM sys_user_resources
            WHERE user_id = %s AND resource_key IN ({placeholders})
        """
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql, (user_id, *resource_keys))
                row = await cursor.fetchone()
        return int(row[0] or 0) == len(resource_keys) if row else False

    @classmethod
    async def sync_user_product_access(cls, user: Dict, product_key: str) -> Dict[str, Any]:
        """已通过审批但 has_access 未生效时，补写资源权限并刷新缓存"""
        user_id = int(user["user_id"])
        status = await cls.get_user_request_status(user_id, product_key)
        if status != "approved":
            raise ValueError("仅已通过审批的申请可同步权限")

        product = await cls._get_raw_product(product_key)
        if not product:
            raise ValueError("产品不存在")

        resource_keys = await cls._get_product_resource_keys(product["id"])
        if not resource_keys:
            raise ValueError("产品未关联 API 资源，请联系负责人配置")

        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                for rk in resource_keys:
                    await cursor.execute(
                        "INSERT IGNORE INTO sys_user_resources (user_id, resource_key) VALUES (%s, %s)",
                        (user_id, rk),
                    )
                await conn.commit()

        await PermissionService.invalidate_user_cache(user_id)
        accessible = await cls._user_resource_keys(user)
        has_access = cls._product_has_access(resource_keys, accessible)
        return {
            "has_access": has_access,
            "resource_keys": resource_keys,
            "granted_count": sum(1 for k in resource_keys if k in accessible),
            "required_count": len(resource_keys),
        }

    @classmethod
    async def _mark_product_requests_revoked(
        cls,
        product_key: str,
        user_id: int,
        handler: Dict,
    ) -> None:
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE data_product_access_requests
                    SET status = %s,
                        handle_remark = CONCAT(
                            IFNULL(handle_remark, ''),
                            IF(IFNULL(handle_remark, '') = '', '', '；'),
                            %s
                        )
                    WHERE product_key = %s AND user_id = %s AND status = %s
                    """,
                    (
                        REQUEST_REVOKED,
                        f"权限已于 {datetime.now().strftime('%Y-%m-%d %H:%M')} 由 {handler.get('user_name', '管理员')} 收回",
                        product_key,
                        user_id,
                        REQUEST_APPROVED,
                    ),
                )
                await conn.commit()

    @classmethod
    async def revoke_product_access(
        cls,
        handler: Dict,
        product_key: str,
        *,
        user_id: Optional[int] = None,
        revoke_all: bool = False,
    ) -> int:
        if not await cls.can_revoke_access(handler, product_key):
            raise PermissionError("无权收回该产品访问权限")
        product = await cls._get_raw_product(product_key)
        if not product:
            raise ValueError("产品不存在")
        resource_keys = await cls._get_product_resource_keys(product["id"])
        if not resource_keys:
            return 0
        if revoke_all:
            holders = await cls.get_product_access_holders(product_key)
            user_ids = [h["user_id"] for h in holders["holders"]]
            removed = await cls._revoke_resources_for_users(resource_keys, user_ids=user_ids)
            for uid in user_ids:
                await cls._mark_product_requests_revoked(product_key, uid, handler)
            return removed
        if not user_id:
            raise ValueError("请指定要收回权限的用户")
        removed = await cls._revoke_resources_for_users(resource_keys, user_ids=[user_id])
        await cls._mark_product_requests_revoked(product_key, user_id, handler)
        return removed

    @classmethod
    async def revoke_access_by_request(cls, request_id: int, handler: Dict) -> int:
        async with get_db_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    """
                    SELECT r.*, p.owner_user_id, p.product_key
                    FROM data_product_access_requests r
                    JOIN data_products p ON p.id = r.product_id
                    WHERE r.id = %s AND r.status = %s
                    """,
                    (request_id, REQUEST_APPROVED),
                )
                req = await cursor.fetchone()
        if not req:
            raise ValueError("申请不存在或未通过审批")
        if not await cls.can_revoke_access(handler, req["product_key"]):
            raise PermissionError("无权收回该用户访问权限")
        return await cls.revoke_product_access(
            handler, req["product_key"], user_id=int(req["user_id"])
        )

    @classmethod
    async def _fetch_redundant_product_rows(cls) -> List[Dict[str, Any]]:
        sql = """
            SELECT
                p.id AS product_id,
                p.product_key,
                p.display_name,
                p.status,
                p.owner_user_id,
                u.user_name AS owner_name,
                pr.resource_key AS duplicate_resource_key,
                host.product_key AS host_product_key,
                host.display_name AS host_display_name,
                host.owner_user_id AS host_owner_user_id
            FROM data_products p
            JOIN data_product_resources pr ON pr.product_id = p.id
            JOIN data_product_resources pr2
                ON pr2.resource_key = pr.resource_key AND pr2.product_id != p.id
            JOIN data_products host ON host.id = pr2.product_id
            LEFT JOIN api_users u ON u.id = p.owner_user_id
            ORDER BY p.updated_at DESC
        """
        async with get_db_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql)
                rows = await cursor.fetchall()
        deduped: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            pk = row["product_key"]
            if pk not in deduped:
                deduped[pk] = row
        return list(deduped.values())

    @classmethod
    async def list_redundant_products(cls, user: Dict) -> List[Dict[str, Any]]:
        rows = await cls._fetch_redundant_product_rows()
        is_admin_user = user.get("role") == "admin"
        perms = user.get("permissions", {}).get("elements", [])
        can_manage = "element:catalog:manage" in perms
        if is_admin_user or can_manage:
            return rows
        uid = int(user["user_id"])
        return [
            r
            for r in rows
            if r.get("owner_user_id") == uid or r.get("host_owner_user_id") == uid
        ]

    @classmethod
    async def get_redundant_product_info(cls, product_key: str) -> Optional[Dict[str, Any]]:
        for row in await cls._fetch_redundant_product_rows():
            if row["product_key"] == product_key:
                return row
        return None

    @classmethod
    async def can_archive_redundant(cls, user: Dict, product_key: str) -> bool:
        info = await cls.get_redundant_product_info(product_key)
        if not info:
            return False
        if user.get("role") == "admin":
            return True
        perms = user.get("permissions", {}).get("elements", [])
        if "element:catalog:manage" in perms:
            return True
        uid = int(user["user_id"])
        return info.get("owner_user_id") == uid or info.get("host_owner_user_id") == uid

    @classmethod
    async def get_resource_duplicate_product(
        cls, resource_key: str, *, exclude_product_key: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """资源曾单独发布为产品（product_key = resource_key）时返回可归档的冗余产品"""
        row = await cls._get_raw_product(resource_key)
        if not row:
            return None
        if exclude_product_key and row["product_key"] == exclude_product_key:
            return None

        host_product_key = exclude_product_key or ""
        host_display_name = exclude_product_key or ""
        if exclude_product_key:
            host_row = await cls._get_raw_product(exclude_product_key)
            if host_row:
                host_display_name = host_row.get("display_name") or exclude_product_key
        else:
            info = await cls.get_redundant_product_info(resource_key)
            if not info:
                return None
            host_product_key = info["host_product_key"]
            host_display_name = info["host_display_name"]

        return {
            "product_key": row["product_key"],
            "display_name": row["display_name"],
            "status": row.get("status", 0),
            "host_product_key": host_product_key,
            "host_display_name": host_display_name,
        }

    @classmethod
    async def check_resource_conflicts(
        cls, resource_keys: List[str], *, host_product_key: str
    ) -> List[Dict[str, Any]]:
        conflicts: List[Dict[str, Any]] = []
        seen: Set[str] = set()
        for key in resource_keys:
            if key in seen:
                continue
            seen.add(key)
            dup = await cls.get_resource_duplicate_product(
                key, exclude_product_key=host_product_key
            )
            if dup:
                conflicts.append(
                    {
                        "product_key": dup["product_key"],
                        "display_name": dup["display_name"],
                        "status": dup.get("status", 0),
                        "duplicate_resource_key": key,
                        "host_product_key": dup["host_product_key"],
                        "host_display_name": dup["host_display_name"],
                    }
                )
        return conflicts

    @classmethod
    async def archive_redundant_product(
        cls,
        user: Dict,
        product_key: str,
        *,
        revoke_permissions: bool = False,
    ) -> Dict[str, Any]:
        info = await cls.get_redundant_product_info(product_key)
        if not info:
            raise ValueError("该产品不是冗余产品，无需归档")
        if not await cls.can_archive_redundant(user, product_key):
            raise PermissionError("无权归档该产品")

        product = await cls._get_raw_product(product_key)
        if not product:
            raise ValueError("产品不存在")

        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT COUNT(*) FROM data_product_access_requests
                    WHERE product_id = %s AND status = %s
                    """,
                    (product["id"], REQUEST_PENDING),
                )
                pending_row = await cursor.fetchone()
                if int(pending_row[0] or 0) > 0:
                    raise ValueError(
                        "该产品仍有待审批的权限申请，请先处理后再归档"
                    )

        if product.get("status") == STATUS_PUBLISHED and revoke_permissions:
            await cls._revoke_all_product_access(product_key)

        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "DELETE FROM data_product_resources WHERE product_id = %s",
                    (product["id"],),
                )
                await cursor.execute(
                    "DELETE FROM data_products WHERE id = %s",
                    (product["id"],),
                )
                await conn.commit()

        return {
            "archived": True,
            "product_key": product_key,
            "host_product_key": info["host_product_key"],
        }

    @classmethod
    async def list_my_access_requests(
        cls, user: Dict, status: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """当前用户提交的目录权限申请"""
        user_id = int(user["user_id"])
        conditions = ["r.user_id = %s"]
        params: List[Any] = [user_id]
        if status is not None:
            conditions.append("r.status = %s")
            params.append(status)

        sql = f"""
            SELECT r.*, p.display_name AS product_name, p.owner_user_id, p.status AS product_status,
                   pr.resource_key AS primary_resource_key, m.resource_group
            FROM data_product_access_requests r
            JOIN data_products p ON p.id = r.product_id
            LEFT JOIN data_product_resources pr ON pr.product_id = p.id AND pr.is_primary = 1
            LEFT JOIN sys_resource_meta m ON {RESOURCE_KEY_JOIN_SQL}
            WHERE {' AND '.join(conditions)}
            ORDER BY r.created_at DESC
            LIMIT 200
        """
        async with get_db_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql, tuple(params))
                rows = await cursor.fetchall()

        status_labels = {
            REQUEST_PENDING: "pending",
            REQUEST_APPROVED: "approved",
            REQUEST_REJECTED: "rejected",
            REQUEST_REVOKED: "revoked",
        }
        for r in rows:
            if r.get("created_at"):
                r["created_at"] = r["created_at"].strftime("%Y-%m-%d %H:%M:%S")
            if r.get("handled_at"):
                r["handled_at"] = r["handled_at"].strftime("%Y-%m-%d %H:%M:%S")
            if r.get("updated_at"):
                r["updated_at"] = r["updated_at"].strftime("%Y-%m-%d %H:%M:%S")
            r["status_label"] = status_labels.get(r.get("status"), "unknown")
            if r.get("status") == REQUEST_APPROVED:
                r["access_active"] = await cls._user_has_product_resource_access(
                    user_id, int(r["product_id"])
                )
            else:
                r["access_active"] = False
        return rows

    @classmethod
    async def count_my_access_requests_by_status(cls, user: Dict) -> Dict[str, int]:
        """当前用户各状态申请数量"""
        user_id = int(user["user_id"])
        sql = """
            SELECT r.status, COUNT(*) AS cnt
            FROM data_product_access_requests r
            WHERE r.user_id = %s
            GROUP BY r.status
        """
        counts = {0: 0, 1: 0, 2: 0, 3: 0}
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql, (user_id,))
                rows = await cursor.fetchall()
        for row in rows:
            status = int(row[0])
            if status in counts:
                counts[status] = int(row[1] or 0)
        total = sum(counts.values())
        return {
            "0": counts[0],
            "1": counts[1],
            "2": counts[2],
            "3": counts[3],
            "all": total,
        }
