"""SQL Lab 增强 API 测试：保存查询、分析会话、异步导出、表收藏"""
import pytest
from httpx import AsyncClient

from app.core.database import get_db_connection


@pytest.fixture(autouse=True)
async def ensure_lab_table_favorites_table():
    ddl = """
    CREATE TABLE IF NOT EXISTS lab_table_favorites (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        source_id INT NOT NULL,
        table_name VARCHAR(255) NOT NULL,
        is_pinned TINYINT(1) DEFAULT 0,
        note VARCHAR(500) NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uk_lab_fav_user_source_table (user_id, source_id, table_name),
        INDEX idx_lab_fav_user_source (user_id, source_id),
        INDEX idx_lab_fav_pinned (user_id, source_id, is_pinned)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """
    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(ddl)
    yield


@pytest.fixture
def admin_auth_headers(admin_api_key):
    return {"X-API-Key": admin_api_key}


async def _get_mysql_source_id(client: AsyncClient, headers: dict) -> int | None:
    res = await client.get("/api/portal/datasource/datasources", headers=headers)
    for ds in res.json():
        if ds.get("source_type") == "mysql":
            return ds["id"]
    if res.json():
        return res.json()[0]["id"]
    return None


@pytest.mark.asyncio
async def test_saved_query_crud(client: AsyncClient, admin_auth_headers):
    source_id = await _get_mysql_source_id(client, admin_auth_headers)
    if not source_id:
        pytest.skip("No datasource")

    create = await client.post(
        "/api/portal/lab/saved-queries",
        json={
            "name": "pytest_saved_query",
            "sql": "SELECT 1 AS n",
            "source_id": source_id,
            "lab_mode": "analyst",
            "tags": ["test", "lab"],
            "is_shared": True,
        },
        headers=admin_auth_headers,
    )
    assert create.status_code == 200
    qid = create.json()["id"]

    listing = await client.get("/api/portal/lab/saved-queries", headers=admin_auth_headers)
    assert listing.status_code == 200
    assert any(q["id"] == qid for q in listing.json())

    update = await client.put(
        f"/api/portal/lab/saved-queries/{qid}",
        json={
            "name": "pytest_saved_query_updated",
            "sql": "SELECT 2 AS n",
            "source_id": source_id,
            "lab_mode": "analyst",
            "tags": ["updated"],
            "is_shared": False,
        },
        headers=admin_auth_headers,
    )
    assert update.status_code == 200

    delete = await client.delete(
        f"/api/portal/lab/saved-queries/{qid}",
        headers=admin_auth_headers,
    )
    assert delete.status_code == 200


@pytest.mark.asyncio
async def test_analysis_session_crud(client: AsyncClient, admin_auth_headers):
    create = await client.post(
        "/api/portal/lab/analysis-sessions",
        json={
            "title": "pytest session",
            "sql": "SELECT 1",
            "columns": [{"name": "n", "type": "int"}],
            "messages": [
                {"role": "user", "content": "分析"},
                {"role": "assistant", "content": "### 标题\n> 引用"},
            ],
        },
        headers=admin_auth_headers,
    )
    assert create.status_code == 200
    sid = create.json()["id"]

    listing = await client.get("/api/portal/lab/analysis-sessions", headers=admin_auth_headers)
    assert listing.status_code == 200
    assert any(s["id"] == sid for s in listing.json())

    detail = await client.get(
        f"/api/portal/lab/analysis-sessions/{sid}",
        headers=admin_auth_headers,
    )
    assert detail.status_code == 200
    assert len(detail.json()["messages_json"]) == 2

    delete = await client.delete(
        f"/api/portal/lab/analysis-sessions/{sid}",
        headers=admin_auth_headers,
    )
    assert delete.status_code == 200


@pytest.mark.asyncio
async def test_table_favorites_crud(client: AsyncClient, admin_auth_headers):
    source_id = await _get_mysql_source_id(client, admin_auth_headers)
    if not source_id:
        pytest.skip("No datasource")

    upsert = await client.put(
        "/api/portal/lab/table-favorites",
        json={
            "source_id": source_id,
            "table_name": "pytest_fav_table",
            "is_pinned": True,
            "note": "常用表",
        },
        headers=admin_auth_headers,
    )
    assert upsert.status_code == 200

    listing = await client.get(
        "/api/portal/lab/table-favorites",
        params={"source_id": source_id},
        headers=admin_auth_headers,
    )
    assert listing.status_code == 200
    fav = next((f for f in listing.json() if f["table_name"] == "pytest_fav_table"), None)
    assert fav is not None
    assert fav["is_pinned"] is True
    assert fav["note"] == "常用表"

    update = await client.put(
        "/api/portal/lab/table-favorites",
        json={
            "source_id": source_id,
            "table_name": "pytest_fav_table",
            "is_pinned": False,
            "note": "更新备注",
        },
        headers=admin_auth_headers,
    )
    assert update.status_code == 200

    delete = await client.delete(
        "/api/portal/lab/table-favorites",
        params={"source_id": source_id, "table_name": "pytest_fav_table"},
        headers=admin_auth_headers,
    )
    assert delete.status_code == 200

    source_id = await _get_mysql_source_id(client, admin_auth_headers)
    if not source_id:
        pytest.skip("No datasource")

    create = await client.post(
        "/api/portal/lab/export",
        json={
            "source_id": source_id,
            "sql": "SELECT 1 AS n LIMIT 1",
            "format": "csv",
        },
        headers=admin_auth_headers,
    )
    assert create.status_code == 200
    job_id = create.json()["job_id"]

    listing = await client.get("/api/portal/lab/export", headers=admin_auth_headers)
    assert listing.status_code == 200
    assert any(j["id"] == job_id for j in listing.json())


@pytest.mark.asyncio
async def test_table_explorer_search_and_tags(client: AsyncClient, admin_auth_headers):
    source_id = await _get_mysql_source_id(client, admin_auth_headers)
    if not source_id:
        pytest.skip("No datasource")

    table_name = "pytest_explorer_search_table"
    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO db_table_profiles
                (connection_id, table_name, table_type, ai_term, ai_description, ai_tags, status, confidence_score)
                VALUES (%s, %s, 'table', '测试探索订单表', 'pytest 探索器关键词订单退款', JSON_ARRAY('交易', 'pytest'), 2, 88)
                ON DUPLICATE KEY UPDATE
                    ai_term=VALUES(ai_term),
                    ai_description=VALUES(ai_description),
                    ai_tags=VALUES(ai_tags),
                    status=VALUES(status),
                    confidence_score=VALUES(confidence_score)
                """,
                (source_id, table_name),
            )

    search = await client.get(
        "/api/portal/lab/table-search",
        params={"source_id": source_id, "q": "探索订单", "page": 1, "page_size": 20},
        headers=admin_auth_headers,
    )
    assert search.status_code == 200
    body = search.json()
    assert body["total"] >= 1
    assert any(item["table_name"] == table_name for item in body["items"])

    tag_res = await client.get(
        "/api/portal/lab/table-tags",
        params={"source_id": source_id},
        headers=admin_auth_headers,
    )
    assert tag_res.status_code == 200
    tags = tag_res.json()
    assert any(t["name"] == "pytest" for t in tags)

    fav = await client.put(
        "/api/portal/lab/table-favorites",
        json={"source_id": source_id, "table_name": table_name, "is_pinned": False, "note": "探索器收藏"},
        headers=admin_auth_headers,
    )
    assert fav.status_code == 200

    fav_search = await client.get(
        "/api/portal/lab/table-search",
        params={"source_id": source_id, "scope": "favorites"},
        headers=admin_auth_headers,
    )
    assert fav_search.status_code == 200
    assert any(item["table_name"] == table_name for item in fav_search.json()["items"])

    await client.delete(
        "/api/portal/lab/table-favorites",
        params={"source_id": source_id, "table_name": table_name},
        headers=admin_auth_headers,
    )
