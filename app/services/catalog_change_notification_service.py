import logging
from typing import Any, Dict, List, Optional

import httpx

from app.core.database import get_db_connection
from app.schemas.catalog_change_notification import (
    CatalogChangeNotificationItem,
    CatalogChangeNotificationListResponse,
)
from app.services.system_service import SystemService

logger = logging.getLogger(__name__)

ACTION_LABELS = {
    "UPDATE": "配置更新",
    "ROLLBACK": "配置回滚",
}


class CatalogChangeNotificationService:
    @classmethod
    async def _is_enabled(cls) -> bool:
        return await SystemService.get_bool_config("catalog.notify_resource_change.enabled", True)

    @classmethod
    async def _get_webhook_url(cls) -> str:
        url = await SystemService.get_config("catalog.notify_resource_change.webhook_url", "")
        return (url or "").strip()

    @classmethod
    async def _find_linked_products(cls, resource_key: str) -> List[Dict[str, Any]]:
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT p.id, p.product_key, p.display_name, p.owner_user_id, p.status
                    FROM data_products p
                    JOIN data_product_resources pr ON pr.product_id = p.id
                    WHERE pr.resource_key = %s
                      AND p.status IN (0, 1)
                      AND p.owner_user_id IS NOT NULL
                    """,
                    (resource_key,),
                )
                rows = await cursor.fetchall()
        return [
            {
                "id": int(row[0]),
                "product_key": row[1],
                "display_name": row[2],
                "owner_user_id": int(row[3]),
                "status": int(row[4]),
            }
            for row in rows
        ]

    @classmethod
    async def notify_on_resource_change(
        cls,
        *,
        resource_key: str,
        resource_name: Optional[str],
        version_id: int,
        action_type: str,
        change_summary: Optional[str],
        operator: Optional[Dict[str, Any]] = None,
    ) -> int:
        if action_type not in ("UPDATE", "ROLLBACK"):
            return 0
        if not await cls._is_enabled():
            return 0

        products = await cls._find_linked_products(resource_key)
        if not products:
            return 0

        operator_user_id = int(operator["user_id"]) if operator and operator.get("user_id") else None
        operator_name = operator.get("user_name") if operator else None
        recipients = [
            p for p in products if p["owner_user_id"] != operator_user_id
        ]
        if not recipients:
            return 0

        created = 0
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                for product in recipients:
                    await cursor.execute(
                        """
                        INSERT INTO data_product_change_notifications
                        (user_id, product_id, product_key, product_display_name, resource_key,
                         resource_name, version_id, action_type, change_summary,
                         operator_user_id, operator_name)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            product["owner_user_id"],
                            product["id"],
                            product["product_key"],
                            product["display_name"],
                            resource_key,
                            resource_name,
                            version_id,
                            action_type,
                            change_summary,
                            operator_user_id,
                            operator_name,
                        ),
                    )
                    created += 1
                await conn.commit()

        if created:
            await cls._send_webhook(
                resource_key=resource_key,
                resource_name=resource_name,
                version_id=version_id,
                action_type=action_type,
                change_summary=change_summary,
                operator_name=operator_name,
                products=recipients,
            )
        return created

    @classmethod
    async def _send_webhook(
        cls,
        *,
        resource_key: str,
        resource_name: Optional[str],
        version_id: int,
        action_type: str,
        change_summary: Optional[str],
        operator_name: Optional[str],
        products: List[Dict[str, Any]],
    ) -> None:
        webhook_url = await cls._get_webhook_url()
        if not webhook_url:
            return

        payload = {
            "event": "resource_config_changed",
            "resource_key": resource_key,
            "resource_name": resource_name,
            "version_id": version_id,
            "action_type": action_type,
            "action_label": ACTION_LABELS.get(action_type, action_type),
            "change_summary": change_summary,
            "operator_name": operator_name,
            "products": [
                {
                    "product_key": p["product_key"],
                    "display_name": p["display_name"],
                    "owner_user_id": p["owner_user_id"],
                }
                for p in products
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
        except Exception as e:
            logger.warning("Catalog change webhook failed: %s", e)

    @staticmethod
    def _map_row(row: tuple) -> CatalogChangeNotificationItem:
        return CatalogChangeNotificationItem(
            id=row[0],
            product_id=row[1],
            product_key=row[2],
            product_display_name=row[3],
            resource_key=row[4],
            resource_name=row[5],
            version_id=row[6],
            action_type=row[7],
            change_summary=row[8],
            operator_name=row[9],
            is_read=bool(row[10]),
            created_at=row[11],
        )

    @classmethod
    async def count_unread(cls, user_id: int) -> int:
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT COUNT(*) FROM data_product_change_notifications
                    WHERE user_id = %s AND is_read = 0
                    """,
                    (user_id,),
                )
                row = await cursor.fetchone()
                return int(row[0] or 0)

    @classmethod
    async def list_notifications(
        cls,
        user_id: int,
        *,
        unread_only: bool = False,
        page: int = 1,
        size: int = 20,
    ) -> CatalogChangeNotificationListResponse:
        page = max(page, 1)
        size = min(max(size, 1), 100)
        offset = (page - 1) * size
        where = "user_id = %s"
        params: List[Any] = [user_id]
        if unread_only:
            where += " AND is_read = 0"

        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    f"SELECT COUNT(*) FROM data_product_change_notifications WHERE {where}",
                    tuple(params),
                )
                total = int((await cursor.fetchone())[0])

                unread = await cls.count_unread(user_id)

                await cursor.execute(
                    f"""
                    SELECT id, product_id, product_key, product_display_name, resource_key,
                           resource_name, version_id, action_type, change_summary,
                           operator_name, is_read, created_at
                    FROM data_product_change_notifications
                    WHERE {where}
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s OFFSET %s
                    """,
                    tuple(params + [size, offset]),
                )
                items = [cls._map_row(row) for row in await cursor.fetchall()]

        return CatalogChangeNotificationListResponse(total=total, unread=unread, items=items)

    @classmethod
    async def mark_read(
        cls,
        user_id: int,
        *,
        ids: Optional[List[int]] = None,
        mark_all: bool = False,
    ) -> int:
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                if mark_all:
                    await cursor.execute(
                        """
                        UPDATE data_product_change_notifications
                        SET is_read = 1
                        WHERE user_id = %s AND is_read = 0
                        """,
                        (user_id,),
                    )
                elif ids:
                    placeholders = ", ".join(["%s"] * len(ids))
                    await cursor.execute(
                        f"""
                        UPDATE data_product_change_notifications
                        SET is_read = 1
                        WHERE user_id = %s AND id IN ({placeholders}) AND is_read = 0
                        """,
                        tuple([user_id] + ids),
                    )
                else:
                    return 0
                affected = cursor.rowcount
                await conn.commit()
                return int(affected or 0)

    @classmethod
    async def get_notify_settings(cls) -> Dict[str, Any]:
        return {
            "notify_resource_change_enabled": await cls._is_enabled(),
            "notify_resource_change_webhook_url": await cls._get_webhook_url(),
        }

    @classmethod
    async def update_notify_settings(
        cls,
        *,
        enabled: bool,
        webhook_url: str,
    ) -> None:
        await SystemService.set_config(
            "catalog.notify_resource_change.enabled",
            "true" if enabled else "false",
            "catalog",
        )
        await SystemService.set_config(
            "catalog.notify_resource_change.webhook_url",
            (webhook_url or "").strip(),
            "catalog",
        )
