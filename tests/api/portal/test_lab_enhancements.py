"""SQL Lab V37 增强 API 测试：保存查询、分析会话、异步导出列表"""
import pytest
from httpx import AsyncClient


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
async def test_export_job_list(client: AsyncClient, admin_auth_headers):
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
