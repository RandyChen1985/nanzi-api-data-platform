import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_list_users_as_admin(client: AsyncClient, admin_api_key: str):
    """Test listing users as admin"""
    response = await client.get(
        "/api/portal/management/users?page=1&size=10",
        headers={"X-API-Key": admin_api_key}
    )
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_list_users_as_non_admin(client: AsyncClient, valid_api_key: str):
        """Test that non-admin users cannot list users"""
        response = await client.get(
            "/api/portal/management/users?page=1&size=10",
            headers={"X-API-Key": valid_api_key}
        )
        assert response.status_code == 403
        assert "Admin access required" in response.json()["message"]
@pytest.mark.asyncio
async def test_list_users_with_search(client: AsyncClient, admin_api_key: str):
    """Test user list search functionality"""
    response = await client.get(
        "/api/portal/management/users?search=test_admin",
        headers={"X-API-Key": admin_api_key}
    )
    assert response.status_code == 200
    data = response.json()
    # Should find at least the admin user
    assert data["total"] >= 1

@pytest.mark.asyncio
async def test_list_users_with_role_filter(client: AsyncClient, admin_api_key: str):
    """Test filtering users by role"""
    response = await client.get(
        "/api/portal/management/users?role=admin",
        headers={"X-API-Key": admin_api_key}
    )
    assert response.status_code == 200
    data = response.json()
    # All returned users should have admin role
    for user in data["items"]:
        assert user["role"] == "admin"

@pytest.mark.asyncio
async def test_create_user_as_admin(client: AsyncClient, admin_api_key: str):
    """Test creating a new user"""
    import time
    unique_username = f"test_user_{int(time.time())}"
    
    response = await client.post(
        "/api/portal/management/users",
        headers={"X-API-Key": admin_api_key},
        json={
            "user_name": unique_username,
            "role": "user",
            "permissions": {"access": ["read"]}
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_name"] == unique_username
    assert data["role"] == "user"
    assert "api_key" in data  # Should return the full API key
    assert len(data["api_key"]) > 20  # Verify it's a real key

    @pytest.mark.asyncio
    async def test_create_duplicate_user(client: AsyncClient, admin_api_key: str):
        """Test that creating duplicate username fails"""
        response = await client.post(
            "/api/portal/management/users",
            headers={"X-API-Key": admin_api_key},
            json={
                "user_name": "test_admin",  # Already exists
                "role": "user"
            }
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["message"].lower()
@pytest.mark.asyncio
async def test_create_user_as_non_admin(client: AsyncClient, valid_api_key: str):
    """Test that non-admin cannot create users"""
    response = await client.post(
        "/api/portal/management/users",
        headers={"X-API-Key": valid_api_key},
        json={
            "user_name": "should_fail",
            "role": "user"
        }
    )
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_update_user_role(client: AsyncClient, admin_api_key: str):
    """Test updating user role"""
    # First create a test user
    import time
    unique_username = f"update_test_{int(time.time())}"
    
    create_response = await client.post(
        "/api/portal/management/users",
        headers={"X-API-Key": admin_api_key},
        json={"user_name": unique_username, "role": "user"}
    )
    user_id = create_response.json()["id"]
    
    # Update role to admin
    response = await client.put(
        f"/api/portal/management/users/{user_id}",
        headers={"X-API-Key": admin_api_key},
        json={"role": "admin"}
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"

@pytest.mark.asyncio
async def test_update_nonexistent_user(client: AsyncClient, admin_api_key: str):
    """Test updating a user that doesn't exist"""
    response = await client.put(
        "/api/portal/management/users/999999",
        headers={"X-API-Key": admin_api_key},
        json={"role": "admin"}
    )
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_disable_user(client: AsyncClient, admin_api_key: str):
    """Test disabling a user"""
    # Create a test user
    import time
    unique_username = f"disable_test_{int(time.time())}"
    
    create_response = await client.post(
        "/api/portal/management/users",
        headers={"X-API-Key": admin_api_key},
        json={"user_name": unique_username, "role": "user"}
    )
    user_id = create_response.json()["id"]
    
    # Disable the user
    response = await client.patch(
        f"/api/portal/management/users/{user_id}/status",
        headers={"X-API-Key": admin_api_key},
        json={"status": 0}
    )
    assert response.status_code == 200
    assert "successfully" in response.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_cannot_disable_self(client: AsyncClient, admin_api_key: str):
        """Test that admin cannot disable themselves"""
        # Get current admin's user ID
        me_response = await client.get(
            "/api/portal/auth/me",
            headers={"X-API-Key": admin_api_key}
        )
        admin_id = int(me_response.json()["data"]["user_id"])
    
        # Try to disable self
        response = await client.patch(
            f"/api/portal/management/users/{admin_id}/status",
            headers={"X-API-Key": admin_api_key},
            json={"status": 0}
        )
        assert response.status_code == 403
        assert "yourself" in response.json()["message"].lower()
@pytest.mark.asyncio
async def test_delete_user(client: AsyncClient, admin_api_key: str):
    """Test deleting a user"""
    # Create a test user
    import time
    unique_username = f"delete_test_{int(time.time())}"
    
    create_response = await client.post(
        "/api/portal/management/users",
        headers={"X-API-Key": admin_api_key},
        json={"user_name": unique_username, "role": "user"}
    )
    user_id = create_response.json()["id"]
    
    # Delete the user
    response = await client.delete(
        f"/api/portal/management/users/{user_id}",
        headers={"X-API-Key": admin_api_key}
    )
    assert response.status_code == 200
    assert "successfully" in response.json()["message"].lower()
    
    # Verify user is deleted
    get_response = await client.get(
        f"/api/portal/management/users?page=1&size=100",
        headers={"X-API-Key": admin_api_key}
    )
    user_ids = [u["id"] for u in get_response.json()["items"]]
    assert user_id not in user_ids

    @pytest.mark.asyncio
    async def test_cannot_delete_self(client: AsyncClient, admin_api_key: str):
        """Test that admin cannot delete themselves"""
        # Get current admin's user ID
        me_response = await client.get(
            "/api/portal/auth/me",
            headers={"X-API-Key": admin_api_key}
        )
        admin_id = int(me_response.json()["data"]["user_id"])
    
        # Try to delete self
        response = await client.delete(
            f"/api/portal/management/users/{admin_id}",
            headers={"X-API-Key": admin_api_key}
        )
        assert response.status_code == 403
        assert "yourself" in response.json()["message"].lower()
@pytest.mark.asyncio
async def test_pagination(client: AsyncClient, admin_api_key: str):
    """Test pagination works correctly"""
    # Get first page
    response1 = await client.get(
        "/api/portal/management/users?page=1&size=5",
        headers={"X-API-Key": admin_api_key}
    )
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["page"] == 1
    assert data1["size"] == 5
    assert len(data1["items"]) <= 5
    
    # If there are more than 5 users, test second page
    if data1["total"] > 5:
        response2 = await client.get(
            "/api/portal/management/users?page=2&size=5",
            headers={"X-API-Key": admin_api_key}
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["page"] == 2
        # Items should be different
        ids1 = {u["id"] for u in data1["items"]}
        ids2 = {u["id"] for u in data2["items"]}
        assert ids1 != ids2


@pytest.mark.asyncio
async def test_reset_user_api_key(client: AsyncClient, admin_api_key: str):
    """Test resetting user api key"""
    # Create user first
    import time
    unique_username = f"reset_key_{int(time.time())}"
    create_response = await client.post(
        "/api/portal/management/users",
        headers={"X-API-Key": admin_api_key},
        json={"user_name": unique_username, "role": "user"}
    )
    assert create_response.status_code == 200
    user_id = create_response.json()["id"]
    old_key = create_response.json()["api_key"]

    # Reset API key
    response = await client.post(
        f"/api/portal/management/users/{user_id}/reset-key",
        headers={"X-API-Key": admin_api_key}
    )
    assert response.status_code == 200
    data = response.json()
    assert "api_key" in data
    assert data["api_key"] != old_key

