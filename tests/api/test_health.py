"""Health endpoint integration tests."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_checks(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data
    assert "checks" in data
    assert "mysql" in data["checks"]
    assert data.get("version") == "1.0.0"
