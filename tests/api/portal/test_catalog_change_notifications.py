"""目录 API 变更通知测试"""
import time

import pytest
from httpx import AsyncClient

from app.core.database import get_db_connection


@pytest.fixture(autouse=True)
async def ensure_notification_tables():
    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sys_resource_meta_versions (
                  id BIGINT NOT NULL AUTO_INCREMENT,
                  resource_key VARCHAR(100) NOT NULL,
                  version_no INT NOT NULL,
                  action_type VARCHAR(32) NOT NULL DEFAULT 'UPDATE',
                  snapshot JSON NOT NULL,
                  change_summary VARCHAR(500) DEFAULT NULL,
                  operator_user_id BIGINT DEFAULT NULL,
                  operator_name VARCHAR(64) DEFAULT NULL,
                  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  UNIQUE KEY uk_resource_version (resource_key, version_no),
                  KEY idx_resource_key_created (resource_key, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS data_product_change_notifications (
                  id BIGINT NOT NULL AUTO_INCREMENT,
                  user_id BIGINT NOT NULL,
                  product_id BIGINT NOT NULL,
                  product_key VARCHAR(100) NOT NULL,
                  product_display_name VARCHAR(200) NOT NULL,
                  resource_key VARCHAR(255) NOT NULL,
                  resource_name VARCHAR(200) DEFAULT NULL,
                  version_id BIGINT DEFAULT NULL,
                  action_type VARCHAR(32) NOT NULL,
                  change_summary VARCHAR(500) DEFAULT NULL,
                  operator_user_id BIGINT DEFAULT NULL,
                  operator_name VARCHAR(64) DEFAULT NULL,
                  is_read TINYINT NOT NULL DEFAULT 0,
                  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  KEY idx_user_read_created (user_id, is_read, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            for key, value in (
                ("catalog.notify_resource_change.enabled", "true"),
                ("catalog.notify_resource_change.webhook_url", ""),
            ):
                await cursor.execute(
                    """
                    INSERT INTO sys_config (config_key, config_value, config_group)
                    VALUES (%s, %s, 'catalog')
                    ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)
                    """,
                    (key, value),
                )
        await conn.commit()


def _sample_resource_payload(resource_key: str) -> dict:
    return {
        "resource_key": resource_key,
        "resource_name": "通知测试资源",
        "resource_group": "测试分组",
        "data_source": "default_clickhouse",
        "resource_mode": "TABLE",
        "table_name": "ck_fact_yunshu_rooms_hbase",
        "custom_sql": None,
        "fields_config": [
            {"name": "rowkey", "label": "行键", "type": "String"},
            {"name": "jfmc", "label": "机房名称", "type": "String"},
        ],
        "allowed_filters": [
            {"name": "jfmc", "label": "机房名称", "type": "String"},
        ],
        "default_sort": "rowkey",
        "status": 1,
        "cache_ttl": 0,
        "remarks": "notify test",
    }


@pytest.mark.asyncio
async def test_resource_change_notifies_product_owner(
    client: AsyncClient, admin_api_key: str, valid_api_key: str
):
    resource_key = f"test_notify_{int(time.time())}"
    admin_headers = {"X-API-Key": admin_api_key}
    user_headers = {"X-API-Key": valid_api_key}

    me = await client.get("/api/portal/auth/me", headers=user_headers)
    assert me.status_code == 200
    owner_user_id = int(me.json()["data"]["user_id"])

    create_resp = await client.post(
        "/api/portal/meta/resources",
        headers=admin_headers,
        json=_sample_resource_payload(resource_key),
    )
    assert create_resp.status_code == 200, create_resp.text

    publish_resp = await client.post(
        "/api/portal/catalog/products/publish-from-resource",
        headers=admin_headers,
        json={"resource_key": resource_key, "publish": True},
    )
    assert publish_resp.status_code == 200

    await client.put(
        f"/api/portal/catalog/products/{resource_key}",
        headers=admin_headers,
        json={"owner_user_id": owner_user_id},
    )

    update_resp = await client.put(
        f"/api/portal/meta/resources/{resource_key}",
        headers=admin_headers,
        json={"resource_name": "通知测试资源-已更新", "remarks": "changed by admin"},
    )
    assert update_resp.status_code == 200

    badge = await client.get(
        "/api/portal/catalog/access-requests/pending-count",
        headers=user_headers,
    )
    assert badge.status_code == 200
    assert badge.json()["change_notification_unread"] >= 1
    assert badge.json()["show_change_notifications_menu"] is True

    notes = await client.get(
        "/api/portal/catalog/change-notifications",
        headers=user_headers,
    )
    assert notes.status_code == 200
    data = notes.json()
    assert data["total"] >= 1
    assert data["unread"] >= 1
    first = data["items"][0]
    assert first["resource_key"] == resource_key
    assert first["action_type"] == "UPDATE"
    assert first["is_read"] is False

    mark = await client.post(
        "/api/portal/catalog/change-notifications/mark-read",
        headers=user_headers,
        json={"ids": [first["id"]]},
    )
    assert mark.status_code == 200
    assert mark.json()["unread"] == data["unread"] - 1

    await client.post(
        f"/api/portal/catalog/products/{resource_key}/unpublish",
        headers=admin_headers,
        json={"revoke_permissions": False},
    )
    await client.delete(f"/api/portal/meta/resources/{resource_key}", headers=admin_headers)


@pytest.mark.asyncio
async def test_resource_change_skips_notify_when_owner_is_operator(
    client: AsyncClient, admin_api_key: str
):
    resource_key = f"test_notify_self_{int(time.time())}"
    admin_headers = {"X-API-Key": admin_api_key}

    me = await client.get("/api/portal/auth/me", headers=admin_headers)
    admin_user_id = int(me.json()["data"]["user_id"])

    await client.post(
        "/api/portal/meta/resources",
        headers=admin_headers,
        json=_sample_resource_payload(resource_key),
    )
    await client.post(
        "/api/portal/catalog/products/publish-from-resource",
        headers=admin_headers,
        json={"resource_key": resource_key, "publish": True},
    )
    await client.put(
        f"/api/portal/catalog/products/{resource_key}",
        headers=admin_headers,
        json={"owner_user_id": admin_user_id},
    )

    await client.put(
        f"/api/portal/meta/resources/{resource_key}",
        headers=admin_headers,
        json={"remarks": "self update"},
    )

    notes = await client.get(
        "/api/portal/catalog/change-notifications",
        headers=admin_headers,
    )
    assert notes.status_code == 200
    matching = [i for i in notes.json()["items"] if i["resource_key"] == resource_key]
    assert matching == []

    await client.post(
        f"/api/portal/catalog/products/{resource_key}/unpublish",
        headers=admin_headers,
        json={"revoke_permissions": False},
    )
    await client.delete(f"/api/portal/meta/resources/{resource_key}", headers=admin_headers)
