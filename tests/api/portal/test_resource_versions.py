import time

import pytest
from httpx import AsyncClient

from app.core.database import get_db_connection


@pytest.fixture(autouse=True)
async def ensure_resource_version_table():
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
        await conn.commit()


def _sample_resource_payload(resource_key: str) -> dict:
    return {
        "resource_key": resource_key,
        "resource_name": "版本测试资源",
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
        "remarks": "version test",
    }


@pytest.mark.asyncio
async def test_resource_version_create_update_and_rollback(
    client: AsyncClient, admin_api_key: str
):
    resource_key = f"test_version_{int(time.time())}"
    headers = {"X-API-Key": admin_api_key}

    create_resp = await client.post(
        "/api/portal/meta/resources",
        headers=headers,
        json=_sample_resource_payload(resource_key),
    )
    assert create_resp.status_code == 200, create_resp.text

    versions_resp = await client.get(
        f"/api/portal/meta/resources/{resource_key}/versions",
        headers=headers,
    )
    assert versions_resp.status_code == 200
    versions_data = versions_resp.json()
    assert versions_data["total"] == 1
    assert versions_data["items"][0]["action_type"] == "CREATE"
    create_version_id = versions_data["items"][0]["id"]

    update_resp = await client.put(
        f"/api/portal/meta/resources/{resource_key}",
        headers=headers,
        json={
            "resource_name": "版本测试资源-已更新",
            "remarks": "updated once",
            "cache_ttl": 30,
        },
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["resource_name"] == "版本测试资源-已更新"

    versions_resp = await client.get(
        f"/api/portal/meta/resources/{resource_key}/versions",
        headers=headers,
    )
    versions_data = versions_resp.json()
    assert versions_data["total"] == 2
    latest = versions_data["items"][0]
    assert latest["action_type"] == "UPDATE"
    assert "资源名称" in (latest.get("change_summary") or "")

    diff_resp = await client.get(
        f"/api/portal/meta/resources/{resource_key}/versions/{create_version_id}/diff",
        headers=headers,
        params={"compare_target": "current"},
    )
    assert diff_resp.status_code == 200
    diff_data = diff_resp.json()
    assert any(item["field"] == "resource_name" for item in diff_data["items"])

    rollback_resp = await client.post(
        f"/api/portal/meta/resources/{resource_key}/versions/{create_version_id}/rollback",
        headers=headers,
    )
    assert rollback_resp.status_code == 200
    rolled = rollback_resp.json()
    assert rolled["resource_name"] == "版本测试资源"
    assert rolled["remarks"] == "version test"
    assert rolled["cache_ttl"] == 0

    versions_resp = await client.get(
        f"/api/portal/meta/resources/{resource_key}/versions",
        headers=headers,
    )
    versions_data = versions_resp.json()
    assert versions_data["total"] == 3
    assert versions_data["items"][0]["action_type"] == "ROLLBACK"

    detail_resp = await client.get(
        f"/api/portal/meta/resources/{resource_key}/versions/{create_version_id}",
        headers=headers,
    )
    assert detail_resp.status_code == 200
    assert detail_resp.json()["snapshot"]["resource_name"] == "版本测试资源"

    await client.delete(f"/api/portal/meta/resources/{resource_key}", headers=headers)


@pytest.mark.asyncio
async def test_resource_version_rollback_requires_edit_permission(
    client: AsyncClient, admin_api_key: str, valid_api_key: str
):
    resource_key = f"test_version_perm_{int(time.time())}"
    admin_headers = {"X-API-Key": admin_api_key}
    user_headers = {"X-API-Key": valid_api_key}

    await client.post(
        "/api/portal/meta/resources",
        headers=admin_headers,
        json=_sample_resource_payload(resource_key),
    )
    versions_resp = await client.get(
        f"/api/portal/meta/resources/{resource_key}/versions",
        headers=admin_headers,
    )
    version_id = versions_resp.json()["items"][0]["id"]

    denied = await client.post(
        f"/api/portal/meta/resources/{resource_key}/versions/{version_id}/rollback",
        headers=user_headers,
    )
    assert denied.status_code == 403

    await client.delete(f"/api/portal/meta/resources/{resource_key}", headers=admin_headers)
