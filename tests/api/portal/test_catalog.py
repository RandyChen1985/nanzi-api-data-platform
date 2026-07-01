"""数据产品目录 API 测试"""
import pytest
from httpx import AsyncClient


def _catalog_items(body):
    if isinstance(body, dict) and "items" in body:
        return body["items"]
    if isinstance(body, list):
        return body
    return []


@pytest.fixture
def admin_headers(admin_api_key):
    return {"X-API-Key": admin_api_key}


@pytest.mark.asyncio
async def test_catalog_products_list(client: AsyncClient, admin_headers: dict):
    response = await client.get("/api/portal/catalog/products", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, (list, dict))
    if isinstance(body, dict):
        assert "items" in body
        assert isinstance(body["items"], list)


@pytest.mark.asyncio
async def test_catalog_domains(client: AsyncClient, admin_headers: dict):
    response = await client.get("/api/portal/catalog/domains", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_catalog_sections(client: AsyncClient, admin_headers: dict):
    response = await client.get("/api/portal/catalog/products/sections", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert "hot" in body
    assert "newest" in body
    assert "featured" in body


@pytest.mark.asyncio
async def test_catalog_panorama_admin(client: AsyncClient, admin_headers: dict):
    response = await client.get("/api/portal/catalog/panorama?days=7", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "published_count" in data
    assert "domain_distribution" in data
    assert "alerts" in data


@pytest.mark.asyncio
async def test_catalog_publish_from_resource(client: AsyncClient, admin_headers: dict):
    resources = await client.get("/api/portal/meta/resources", headers=admin_headers)
    assert resources.status_code == 200
    items = resources.json()
    target = next(
        (r for r in items if r.get("resource_group", "").lower() != "system" and r.get("resource_mode") in ("TABLE", "SQL")),
        None,
    )
    if not target:
        pytest.skip("无可用非系统资源")
    response = await client.post(
        "/api/portal/catalog/products/publish-from-resource",
        headers=admin_headers,
        json={"resource_key": target["resource_key"], "publish": True},
    )
    assert response.status_code == 200
    assert response.json().get("product_key") == target["resource_key"]

    detail = await client.get(
        f"/api/portal/catalog/products/{target['resource_key']}",
        headers=admin_headers,
    )
    assert detail.status_code == 200
    assert detail.json()["display_name"] == target["resource_name"]


@pytest.mark.asyncio
async def test_catalog_status_map(client: AsyncClient, admin_headers: dict):
    response = await client.get("/api/portal/catalog/status-map", headers=admin_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


@pytest.mark.asyncio
async def test_catalog_batch_publish_returns_skipped(client: AsyncClient, admin_headers: dict):
    response = await client.post("/api/portal/catalog/products/batch-publish", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "published" in data
    assert "skipped" in data
    assert isinstance(data["skipped"], list)


@pytest.mark.asyncio
async def test_catalog_update_and_edit_meta(client: AsyncClient, admin_headers: dict):
    products = await client.get("/api/portal/catalog/products?include_draft=true", headers=admin_headers)
    items = _catalog_items(products.json())
    if products.status_code != 200 or not items:
        pytest.skip("无目录产品")
    key = items[0]["product_key"]
    meta = await client.get(f"/api/portal/catalog/products/{key}/edit-meta", headers=admin_headers)
    assert meta.status_code == 200
    assert meta.json().get("can_edit") is True

    update = await client.put(
        f"/api/portal/catalog/products/{key}",
        headers=admin_headers,
        json={"summary": "自动化测试简介", "owner_user_id": 1},
    )
    assert update.status_code == 200


@pytest.mark.asyncio
async def test_catalog_mine_summary(client: AsyncClient, admin_headers: dict):
    response = await client.get("/api/portal/catalog/products/mine-summary", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "owned_products" in data
    assert "pending_review" in data


@pytest.mark.asyncio
async def test_catalog_only_no_access_filter(client: AsyncClient, admin_headers: dict):
    response = await client.get(
        "/api/portal/catalog/products",
        headers=admin_headers,
        params={"only_no_access": True},
    )
    assert response.status_code == 200
    for item in _catalog_items(response.json()):
        assert item.get("has_access") is False


@pytest.mark.asyncio
async def test_catalog_export_csv(client: AsyncClient, admin_headers: dict):
    response = await client.get("/api/portal/catalog/products/export", headers=admin_headers)
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")
    assert "产品Key" in response.text


@pytest.mark.asyncio
async def test_catalog_pending_count_extended(client: AsyncClient, admin_headers: dict):
    response = await client.get("/api/portal/catalog/access-requests/pending-count", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "show_requests_menu" in data


@pytest.mark.asyncio
async def test_catalog_access_request_status_counts(client: AsyncClient, admin_headers: dict):
    response = await client.get("/api/portal/catalog/access-requests/status-counts", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    for key in ("0", "1", "2", "3", "all"):
        assert key in data
        assert isinstance(data[key], int)


@pytest.mark.asyncio
async def test_catalog_my_access_request_status_counts(client: AsyncClient, admin_headers: dict):
    response = await client.get("/api/portal/catalog/access-requests/mine/status-counts", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    for key in ("0", "1", "2", "3", "all"):
        assert key in data
        assert isinstance(data[key], int)


@pytest.mark.asyncio
async def test_catalog_batch_assign_owner(client: AsyncClient, admin_headers: dict):
    products = await client.get(
        "/api/portal/catalog/products?include_draft=true",
        headers=admin_headers,
    )
    items = _catalog_items(products.json())
    if not items:
        pytest.skip("无目录产品")
    key = items[0]["product_key"]
    users = await client.get("/api/portal/catalog/assign-owner-users", headers=admin_headers)
    assert users.status_code == 200
    assert len(users.json()) > 0
    owner_id = users.json()[0]["id"]
    res = await client.post(
        "/api/portal/catalog/products/batch-assign-owner",
        headers=admin_headers,
        json={"owner_user_id": owner_id, "product_keys": [key], "only_without_owner": False},
    )
    assert res.status_code == 200
    assert res.json().get("updated", 0) >= 1


@pytest.mark.asyncio
async def test_catalog_access_requests_all_status(client: AsyncClient, admin_headers: dict):
    """不传 status 应返回全部状态的申请"""
    response = await client.get("/api/portal/catalog/access-requests", headers=admin_headers)
    assert response.status_code == 200
    pending = await client.get("/api/portal/catalog/access-requests", headers=admin_headers, params={"status": 0})
    approved = await client.get("/api/portal/catalog/access-requests", headers=admin_headers, params={"status": 1})
    all_items = response.json()
    assert len(all_items) >= len(pending.json()) + len(approved.json()) or (not pending.json() and not approved.json())


@pytest.mark.asyncio
async def test_catalog_access_request_flow(client: AsyncClient, admin_headers: dict):
    products = await client.get("/api/portal/catalog/products", headers=admin_headers)
    items = _catalog_items(products.json())
    if not items:
        pytest.skip("无已发布产品")
    key = items[0]["product_key"]
    if items[0].get("has_access"):
        pytest.skip("管理员已有权限，跳过申请流程测试")

    create = await client.post(
        f"/api/portal/catalog/products/{key}/access-request",
        headers=admin_headers,
        json={"message": "测试申请"},
    )
    assert create.status_code in (200, 400)

    pending = await client.get("/api/portal/catalog/access-requests", headers=admin_headers)
    assert pending.status_code == 200
    assert isinstance(pending.json(), list)


@pytest.mark.asyncio
async def test_catalog_products_pagination(client: AsyncClient, admin_headers: dict):
    response = await client.get(
        "/api/portal/catalog/products",
        headers=admin_headers,
        params={"page": 1, "page_size": 10},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["page"] == 1
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_catalog_unpublish_preview(client: AsyncClient, admin_headers: dict):
    products = await client.get(
        "/api/portal/catalog/products?include_draft=true",
        headers=admin_headers,
    )
    items = _catalog_items(products.json())
    if not items:
        pytest.skip("无目录产品")
    key = items[0]["product_key"]
    response = await client.get(
        f"/api/portal/catalog/products/{key}/unpublish-preview",
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert "count" in body
    assert "holders" in body


@pytest.mark.asyncio
async def test_catalog_settings_get_and_put(client: AsyncClient, admin_headers: dict):
    get_res = await client.get("/api/portal/catalog/settings", headers=admin_headers)
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["default_owner_strategy"] in ("publisher", "group_owner", "none")
    assert isinstance(data["group_owner_map"], dict)

    put_res = await client.put(
        "/api/portal/catalog/settings",
        headers=admin_headers,
        json={"default_owner_strategy": "publisher", "group_owner_map": {}},
    )
    assert put_res.status_code == 200
    assert put_res.json()["default_owner_strategy"] == "publisher"


@pytest.mark.asyncio
async def test_catalog_update_product_resources(client: AsyncClient, admin_headers: dict):
    products = await client.get(
        "/api/portal/catalog/products?include_draft=true",
        headers=admin_headers,
    )
    items = _catalog_items(products.json())
    if not items:
        pytest.skip("无目录产品")
    key = items[0]["product_key"]
    detail = await client.get(f"/api/portal/catalog/products/{key}", headers=admin_headers)
    assert detail.status_code == 200
    resources = detail.json().get("resources") or []
    if not resources:
        pytest.skip("产品无关联资源")
    payload = [
        {"resource_key": r["resource_key"], "is_primary": bool(r.get("is_primary"))}
        for r in resources
    ]
    res = await client.put(
        f"/api/portal/catalog/products/{key}/resources",
        headers=admin_headers,
        json={"resources": payload},
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_catalog_my_access_requests(client: AsyncClient, admin_headers: dict):
    response = await client.get("/api/portal/catalog/access-requests/mine", headers=admin_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_catalog_redundant_products_list(client: AsyncClient, admin_headers: dict):
    response = await client.get("/api/portal/catalog/products/redundant", headers=admin_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_catalog_resource_conflicts(client: AsyncClient, admin_headers: dict):
    products = await client.get(
        "/api/portal/catalog/products?include_draft=true",
        headers=admin_headers,
    )
    items = _catalog_items(products.json())
    if not items:
        pytest.skip("无目录产品")
    key = items[0]["product_key"]
    detail = await client.get(f"/api/portal/catalog/products/{key}", headers=admin_headers)
    resources = detail.json().get("resources") or []
    if not resources:
        pytest.skip("产品无关联资源")
    keys = ",".join(r["resource_key"] for r in resources)
    response = await client.get(
        f"/api/portal/catalog/products/{key}/resource-conflicts",
        headers=admin_headers,
        params={"keys": keys},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_catalog_sync_access_after_approve(client: AsyncClient, admin_headers: dict):
    products = await client.get("/api/portal/catalog/products", headers=admin_headers)
    items = _catalog_items(products.json())
    if not items:
        pytest.skip("无已发布产品")
    key = items[0]["product_key"]
    if items[0].get("has_access"):
        pytest.skip("管理员已有权限")
    create = await client.post(
        f"/api/portal/catalog/products/{key}/access-request",
        headers=admin_headers,
        json={"message": "sync test"},
    )
    if create.status_code not in (200, 400):
        pytest.skip("无法创建申请")
    pending = await client.get(
        "/api/portal/catalog/access-requests",
        headers=admin_headers,
        params={"status": 0},
    )
    req = next((r for r in pending.json() if r.get("product_key") == key), None)
    if not req:
        pytest.skip("无待审批申请")
    approve = await client.post(
        f"/api/portal/catalog/access-requests/{req['id']}/approve",
        headers=admin_headers,
        json={},
    )
    assert approve.status_code == 200
    sync = await client.post(
        f"/api/portal/catalog/products/{key}/sync-access",
        headers=admin_headers,
    )
    assert sync.status_code == 200
    body = sync.json()
    assert "has_access" in body
    assert body.get("required_count", 0) >= 1


@pytest.mark.asyncio
async def test_catalog_linked_resource_versions(client: AsyncClient, admin_headers: dict):
    import time
    from app.core.database import get_db_connection

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

    resource_key = f"test_cat_link_ver_{int(time.time())}"
    payload = {
        "resource_key": resource_key,
        "resource_name": "目录关联版本测试",
        "resource_group": "测试分组",
        "data_source": "default_clickhouse",
        "resource_mode": "TABLE",
        "table_name": "ck_fact_yunshu_rooms_hbase",
        "custom_sql": None,
        "fields_config": [{"name": "rowkey", "label": "行键", "type": "String"}],
        "allowed_filters": [],
        "default_sort": "rowkey",
        "status": 1,
        "cache_ttl": 0,
        "remarks": "catalog version test",
    }
    create = await client.post("/api/portal/meta/resources", headers=admin_headers, json=payload)
    assert create.status_code == 200

    publish = await client.post(
        "/api/portal/catalog/products/publish-from-resource",
        headers=admin_headers,
        json={"resource_key": resource_key, "publish": False},
    )
    assert publish.status_code == 200
    product_key = publish.json()["product_key"]

    update = await client.put(
        f"/api/portal/meta/resources/{resource_key}",
        headers=admin_headers,
        json={"resource_name": "目录关联版本测试-更新"},
    )
    assert update.status_code == 200

    versions = await client.get(
        f"/api/portal/catalog/products/{product_key}/linked-resource-versions",
        headers=admin_headers,
        params={"keys": resource_key, "limit": 5},
    )
    assert versions.status_code == 200
    data = versions.json()
    assert data["product_key"] == product_key
    assert len(data["resources"]) == 1
    assert data["resources"][0]["resource_key"] == resource_key
    assert data["resources"][0]["total_versions"] >= 2
    assert len(data["resources"][0]["recent_versions"]) >= 2

@pytest.mark.asyncio
async def test_catalog_linked_resource_versions_readonly_user(
    client: AsyncClient, admin_headers: dict, valid_api_key: str
):
    products = await client.get("/api/portal/catalog/products", headers={"X-API-Key": valid_api_key})
    items = _catalog_items(products.json())
    if not items:
        pytest.skip("无已发布产品")
    key = items[0]["product_key"]
    user_headers = {"X-API-Key": valid_api_key}
    response = await client.get(
        f"/api/portal/catalog/products/{key}/linked-resource-versions",
        headers=user_headers,
    )
    assert response.status_code == 200
    assert response.json()["product_key"] == key


@pytest.mark.asyncio
async def test_catalog_linked_resource_versions_rejects_unlinked_key_for_user(
    client: AsyncClient, admin_headers: dict, valid_api_key: str
):
    products = await client.get("/api/portal/catalog/products", headers={"X-API-Key": valid_api_key})
    items = _catalog_items(products.json())
    if not items:
        pytest.skip("无已发布产品")
    key = items[0]["product_key"]
    response = await client.get(
        f"/api/portal/catalog/products/{key}/linked-resource-versions",
        headers={"X-API-Key": valid_api_key},
        params={"keys": "totally_unrelated_resource_key"},
    )
    assert response.status_code == 200
    assert response.json()["resources"] == []
