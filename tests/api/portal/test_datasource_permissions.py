import pytest
from httpx import AsyncClient
from app.core.database import get_db_connection


@pytest.fixture
def admin_headers(admin_api_key):
    return {"X-API-Key": admin_api_key}


@pytest.mark.asyncio
async def test_get_datasource_permissions(client: AsyncClient, admin_headers):
    test_role_id = 7771
    test_user_id = 7772
    source_name = "perm_view_test_ds"

    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "DELETE FROM sys_ui_permissions WHERE user_id = %s OR role_id = %s",
                (test_user_id, test_role_id),
            )
            await cursor.execute(
                "DELETE FROM sys_user_role_relation WHERE user_id = %s",
                (test_user_id,),
            )
            await cursor.execute("DELETE FROM sys_roles WHERE id = %s", (test_role_id,))
            await cursor.execute("DELETE FROM api_users WHERE id = %s", (test_user_id,))
            await cursor.execute(
                "DELETE FROM sys_data_source WHERE source_name = %s",
                (source_name,),
            )

            await cursor.execute(
                """
                INSERT INTO sys_data_source
                (source_name, source_type, host, port, status, sort_order)
                VALUES (%s, 'mysql', 'localhost', 3306, 1, 0)
                """,
                (source_name,),
            )
            source_id = cursor.lastrowid

            await cursor.execute(
                "INSERT INTO sys_roles (id, role_code, role_name) VALUES (%s, %s, %s)",
                (test_role_id, "perm_view_role", "授权查看测试角色"),
            )
            await cursor.execute(
                """
                INSERT INTO api_users (id, user_name, role, status, api_key_hash)
                VALUES (%s, %s, 'user', 1, 'perm_view_hash')
                """,
                (test_user_id, "perm_view_user"),
            )
            await cursor.execute(
                "INSERT INTO sys_user_role_relation (user_id, role_id) VALUES (%s, %s)",
                (test_user_id, test_role_id),
            )
            await cursor.execute(
                """
                INSERT INTO sys_ui_permissions (role_id, perm_type, perm_code)
                VALUES (%s, 'datasource', %s)
                """,
                (test_role_id, f"ds:{source_name}"),
            )
            await cursor.execute(
                """
                INSERT INTO sys_ui_permissions (role_id, perm_type, perm_code)
                VALUES (%s, 'data_table', %s)
                """,
                (test_role_id, f"ds:{source_name}:table:*"),
            )
            await cursor.execute(
                """
                INSERT INTO sys_ui_permissions (user_id, perm_type, perm_code)
                VALUES (%s, 'datasource', %s)
                """,
                (test_user_id, f"ds:{source_name}"),
            )
            await cursor.execute(
                """
                INSERT INTO sys_ui_permissions (user_id, perm_type, perm_code)
                VALUES (%s, 'data_table', %s)
                """,
                (test_user_id, f"ds:{source_name}:table:orders"),
            )
            await conn.commit()

    try:
        resp = await client.get(
            f"/api/portal/datasource/datasources/{source_id}/permissions",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_name"] == source_name
        assert len(data["roles"]) == 1
        assert data["roles"][0]["role_code"] == "perm_view_role"
        assert data["roles"][0]["member_count"] == 1
        assert data["roles"][0]["table_scope"]["all_tables"] is True

        assert len(data["users"]) == 1
        assert data["users"][0]["user_name"] == "perm_view_user"
        assert data["users"][0]["table_scope"]["tables"] == ["orders"]
        assert data["admin_count"] >= 1
    finally:
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "DELETE FROM sys_ui_permissions WHERE user_id = %s OR role_id = %s",
                    (test_user_id, test_role_id),
                )
                await cursor.execute(
                    "DELETE FROM sys_user_role_relation WHERE user_id = %s",
                    (test_user_id,),
                )
                await cursor.execute("DELETE FROM sys_roles WHERE id = %s", (test_role_id,))
                await cursor.execute("DELETE FROM api_users WHERE id = %s", (test_user_id,))
                await cursor.execute(
                    "DELETE FROM sys_data_source WHERE source_name = %s",
                    (source_name,),
                )
                await conn.commit()
