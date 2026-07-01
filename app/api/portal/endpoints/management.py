from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel
from typing import Optional, Dict
from app.core.dependencies import require_admin, require_api_key, require_permission
from app.core.database import get_db_connection
from app.services.auth_service import AuthService
import json

# Admin-only router
router = APIRouter()

# Request/Response Models
class CreateUserRequest(BaseModel):
    user_name: str
    role: str = "user"  # "admin" or "user"
    allowed_resources: Optional[list] = []
    menus: Optional[list] = []
    elements: Optional[list] = []
    remark: Optional[str] = None
    rate_limit: Optional[int] = None

class UpdateUserRequest(BaseModel):
    role: Optional[str] = None
    allowed_resources: Optional[list] = None
    role_ids: Optional[list] = None
    menus: Optional[list] = []
    elements: Optional[list] = []
    datasources: Optional[list] = [] # 新增
    data_tables: Optional[list] = [] # 新增
    remark: Optional[str] = None
    rate_limit: Optional[int] = None
    masking_strategy: Optional[str] = None



class UpdateStatusRequest(BaseModel):
    status: int  # 1=enabled, 0=disabled

class RoleCreateRequest(BaseModel):
    role_code: str
    role_name: str
    description: Optional[str] = None
    masking_strategy: Optional[str] = "GLOBAL"

@router.get("/roles", response_model=list)
async def list_available_roles(admin: dict = Depends(require_admin)):
    """List all defined business roles with permission counts"""
    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            # 1. Fetch Roles
            await cursor.execute(
                "SELECT id, role_code, role_name, description, created_at, masking_strategy, rate_limit "
                "FROM sys_roles ORDER BY created_at DESC"
            )
            role_rows = await cursor.fetchall()
            
            # 2. Fetch Counts for all roles at once (Permissions)
            await cursor.execute("""
                SELECT role_id, perm_type, COUNT(*) 
                FROM sys_ui_permissions 
                WHERE role_id IS NOT NULL 
                GROUP BY role_id, perm_type
            """)
            count_rows = await cursor.fetchall()
            
            # 3. Fetch User Counts for all roles
            await cursor.execute("""
                SELECT role_id, COUNT(*) 
                FROM sys_user_role_relation 
                GROUP BY role_id
            """)
            user_count_rows = await cursor.fetchall()
            user_counts = {rid: cnt for rid, cnt in user_count_rows}

            # Organize counts
            # role_id -> {type -> count}
            stats_map = {}
            for rid, ptype, cnt in count_rows:
                if rid not in stats_map: stats_map[rid] = {"menu": 0, "element": 0, "resource": 0, "user": 0}
                stats_map[rid][ptype] = cnt
            
            # Merge user counts
            for rid, cnt in user_counts.items():
                if rid not in stats_map: stats_map[rid] = {"menu": 0, "element": 0, "resource": 0, "user": 0}
                stats_map[rid]["user"] = cnt

            results = []
            for row in role_rows:
                rid = row[0]
                stats = stats_map.get(rid, {"menu": 0, "element": 0, "resource": 0, "user": 0})
                results.append({
                    "id": rid,
                    "role_code": row[1],
                    "role_name": row[2],
                    "description": row[3],
                    "created_at": row[4],
                    "masking_strategy": row[5],
                    "rate_limit": row[6],
                    "stats": stats
                })
            return results


@router.post("/roles")
async def create_business_role(request: RoleCreateRequest, admin: dict = Depends(require_admin)):
    """Create a new business role"""
    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            try:
                await cursor.execute(
                    "INSERT INTO sys_roles (role_code, role_name, description, masking_strategy) VALUES (%s, %s, %s, %s)",
                    (request.role_code, request.role_name, request.description, request.masking_strategy)
                )
                await conn.commit()
                return {"message": "Role created successfully"}
            except Exception as e:
                if "Duplicate entry" in str(e):
                    raise HTTPException(status_code=400, detail="Role code already exists")
                raise HTTPException(status_code=500, detail=str(e))
@router.put("/roles/{role_id}")
async def update_business_role(role_id: int, request: RoleCreateRequest, admin: dict = Depends(require_admin)):
    """Update role name and description"""
    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "UPDATE sys_roles SET role_name = %s, description = %s, masking_strategy = %s WHERE id = %s",
                (request.role_name, request.description, request.masking_strategy, role_id)
            )
            await conn.commit()
            return {"message": "Role updated successfully"}

@router.delete("/roles/{role_id}")
async def delete_business_role(role_id: int, admin: dict = Depends(require_admin)):
    """Delete a role and its relations"""
    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            # 1. Delete relations
            await cursor.execute("DELETE FROM sys_user_role_relation WHERE role_id = %s", (role_id,))
            # 2. Delete permissions
            await cursor.execute("DELETE FROM sys_ui_permissions WHERE role_id = %s", (role_id,))
            # 3. Delete role
            await cursor.execute("DELETE FROM sys_roles WHERE id = %s", (role_id,))
            await conn.commit()
            return {"message": "Role deleted successfully"}

@router.get("/roles/{role_id}/permissions")
async def get_role_ui_permissions(role_id: int, admin: dict = Depends(require_admin)):
    """Fetch UI and Data Asset permissions for a role"""
    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT perm_type, perm_code FROM sys_ui_permissions WHERE role_id = %s",
                (role_id,)
            )
            rows = await cursor.fetchall()
            res = {"menus": [], "elements": [], "resources": [], "datasources": [], "data_tables": [], "rate_limit": None}
            for p_type, p_code in rows:
                if p_type == 'menu': res["menus"].append(p_code)
                elif p_type == 'element': res["elements"].append(p_code)
                elif p_type == 'resource': res["resources"].append(p_code)
                elif p_type == 'datasource': res["datasources"].append(p_code)
                elif p_type == 'data_table': res["data_tables"].append(p_code)
            await cursor.execute("SELECT rate_limit FROM sys_roles WHERE id = %s", (role_id,))
            rate_row = await cursor.fetchone()
            if rate_row:
                res["rate_limit"] = rate_row[0]
            return res

@router.get("/roles/{role_id}/users")
async def get_role_users(role_id: int, admin: dict = Depends(require_admin)):
    """Fetch all user IDs currently assigned to this role"""
    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT user_id FROM sys_user_role_relation WHERE role_id = %s",
                (role_id,)
            )
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

class UpdateRoleUsersRequest(BaseModel):
    user_ids: list = []

@router.put("/roles/{role_id}/users")
async def update_role_users(role_id: int, request: UpdateRoleUsersRequest, admin: dict = Depends(require_admin)):
    """Update role membership (full replacement)"""
    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            # 1. Verify role exists
            await cursor.execute("SELECT id FROM sys_roles WHERE id = %s", (role_id,))
            if not await cursor.fetchone():
                raise HTTPException(status_code=404, detail="Role not found")

            # 2. Get current members BEFORE deletion (to invalidate their cache later)
            await cursor.execute("SELECT user_id FROM sys_user_role_relation WHERE role_id = %s", (role_id,))
            old_member_ids = [r[0] for r in await cursor.fetchall()]

            # 3. Verify all new user_ids exist if provided
            new_member_ids = list(set(request.user_ids))
            if new_member_ids:
                format_strings = ','.join(['%s'] * len(new_member_ids))
                await cursor.execute(
                    f"SELECT id FROM api_users WHERE id IN ({format_strings})",
                    tuple(new_member_ids)
                )
                existing_users = await cursor.fetchall()
                if len(existing_users) != len(new_member_ids):
                    raise HTTPException(status_code=400, detail="One or more user IDs are invalid")

            # 4. Full replacement strategy
            # Clear existing members
            await cursor.execute("DELETE FROM sys_user_role_relation WHERE role_id = %s", (role_id,))
            
            # Batch Add new members
            if new_member_ids:
                user_values = [(uid, role_id) for uid in new_member_ids]
                await cursor.executemany(
                    "INSERT INTO sys_user_role_relation (user_id, role_id) VALUES (%s, %s)",
                    user_values
                )
            
            await conn.commit()
            
            # 5. Invalidate cache for ALL affected users (Old + New)
            # This ensures users removed from the role lose permissions immediately,
            # and users added to the role gain them immediately.
            from app.services.permission_service import PermissionService
            affected_user_ids = list(set(old_member_ids + new_member_ids))
            
            for uid in affected_user_ids:
                await PermissionService.invalidate_user_cache(uid)
            
            return {"message": "Role members updated successfully"}

class UpdateRolePermissionsRequest(BaseModel):
    menus: list = []
    elements: list = []
    resources: list = []
    datasources: list = [] # 新增
    data_tables: list = [] # 新增
    rate_limit: Optional[int] = None

@router.put("/roles/{role_id}/permissions")
async def update_role_ui_permissions(role_id: int, request: UpdateRolePermissionsRequest, admin: dict = Depends(require_admin)):
    """Update UI, Resource, and Data Asset permissions for a role"""
    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            # 1. Update rate_limit in sys_roles
            if request.rate_limit is not None:
                await cursor.execute(
                    "UPDATE sys_roles SET rate_limit = %s WHERE id = %s",
                    (request.rate_limit, role_id)
                )

            # 2. Clear existing permissions
            await cursor.execute("DELETE FROM sys_ui_permissions WHERE role_id = %s", (role_id,))
            
            # 3. Batch Add permissions
            all_perms = []
            for m in request.menus: all_perms.append((role_id, 'menu', m))
            for e in request.elements: all_perms.append((role_id, 'element', e))
            for r in request.resources: all_perms.append((role_id, 'resource', r))
            for d in request.datasources: all_perms.append((role_id, 'datasource', d))
            for t in request.data_tables: all_perms.append((role_id, 'data_table', t))
            
            if all_perms:
                await cursor.executemany(
                    "INSERT INTO sys_ui_permissions (role_id, perm_type, perm_code) VALUES (%s, %s, %s)",
                    all_perms
                )
            
            await conn.commit()
            
            # Invalidate cache for ALL users in this role
            from app.services.permission_service import PermissionService
            await PermissionService.invalidate_role_cache(role_id)
            
            return {"message": "Role permissions updated successfully"}



@router.get("/users/{user_id}/permissions")


async def get_user_ui_permissions(user_id: int, admin: dict = Depends(require_admin)):


    """Fetch both direct and inherited permissions for a user"""


    from app.services.permission_service import PermissionService


    # 1. Get Aggregated (Direct + Role Inherited)


    full_perms = await PermissionService.get_user_permissions(user_id)


    


    # 2. Get Direct only (for editing)


    async with get_db_connection() as conn:


        async with conn.cursor() as cursor:


                        await cursor.execute(
                            "SELECT perm_type, perm_code FROM sys_ui_permissions WHERE user_id = %s AND role_id IS NULL",
                            (user_id,)
                        )
                        rows = await cursor.fetchall()
                        direct = {"menus": [], "elements": [], "resources": [], "datasources": [], "data_tables": []}
                        for p_type, p_code in rows:
                            if p_type == 'menu': direct["menus"].append(p_code)
                            elif p_type == 'element': direct["elements"].append(p_code)
                            elif p_type == 'resource': direct["resources"].append(p_code)
                            elif p_type == 'datasource': direct["datasources"].append(p_code)
                            elif p_type == 'data_table': direct["data_tables"].append(p_code)
                        
                        return {
                            "direct": direct,
                            "aggregated": {
                                "menus": full_perms.permissions.menus,
                                "elements": full_perms.permissions.elements,
                                "resources": full_perms.permissions.resources,
                                "datasources": full_perms.permissions.datasources,
                                "data_tables": full_perms.permissions.data_tables
                            }
                        }
            
            




@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=1000),
    search: Optional[str] = None,
    role: Optional[str] = Query(None),
    status_filter: Optional[int] = Query(None, alias="status"),
    user: dict = Depends(require_permission("element:user:manage"))
):

    """
    List all users with pagination and filters.
    Admin only.
    """
    offset = (page - 1) * size
    
    query_conditions = []
    params = []
    
    if search:
        query_conditions.append("user_name LIKE %s")
        params.append(f"%{search}%")
    
    if role and role in ["admin", "user"]:
        query_conditions.append("role = %s")
        params.append(role)
    
    if status_filter is not None:
        query_conditions.append("status = %s")
        params.append(status_filter)
        
    where_clause = ""
    if query_conditions:
        where_clause = "WHERE " + " AND ".join(query_conditions)
        
    sql_count = f"SELECT count(*) FROM api_users {where_clause}"
    sql_query = f"""
        SELECT id, user_name, role, remark, status, created_at, updated_at, rate_limit, masking_strategy
        FROM api_users 
        {where_clause} 
        ORDER BY created_at DESC 
        LIMIT %s OFFSET %s
    """
    
    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            # Get Total
            await cursor.execute(sql_count, tuple(params))
            total = (await cursor.fetchone())[0]
            
            # Get Data
            query_params = tuple(params + [size, offset])
            await cursor.execute(sql_query, query_params)
            rows = await cursor.fetchall()
            
            # Format results
            columns = [col[0] for col in cursor.description]
            items = [dict(zip(columns, row)) for row in rows]
            
            # Populate allowed_resources from sys_user_resources
            user_ids = [item["id"] for item in items]
            if user_ids:
                format_strings = ','.join(['%s'] * len(user_ids))
                await cursor.execute(
                    f"SELECT user_id, resource_key FROM sys_user_resources WHERE user_id IN ({format_strings})",
                    tuple(user_ids)
                )
                res_rows = await cursor.fetchall()
                
                # Map user_id -> [resources]
                res_map = {}
                for uid, rkey in res_rows:
                    if uid not in res_map:
                        res_map[uid] = []
                    res_map[uid].append(rkey)
                
                # Merge into items as allowed_resources
                for item in items:
                    item["allowed_resources"] = res_map.get(item["id"], [])

            # Populate role_ids from sys_user_role_relation
            if user_ids:
                format_strings = ','.join(['%s'] * len(user_ids))
                await cursor.execute(
                    f"SELECT user_id, role_id FROM sys_user_role_relation WHERE user_id IN ({format_strings})",
                    tuple(user_ids)
                )
                role_rows = await cursor.fetchall()
                role_map = {}
                for uid, rid in role_rows:
                    if uid not in role_map: role_map[uid] = []
                    role_map[uid].append(rid)
                for item in items:
                    item["role_ids"] = role_map.get(item["id"], [])

            return {

                "total": total,
                "page": page,
                "size": size,
                "items": items
            }

@router.post("/users")

async def create_user(request: CreateUserRequest, user: dict = Depends(require_permission("element:user:manage"))):
    """
    Create a new user with API key.
    Admin only.
    """
    # Validate role
    if request.role not in ["admin", "user"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be 'admin' or 'user'"
        )
    
    try:
        # Generate API key
        api_key = await AuthService.generate_api_key(
            request.user_name,
            role=request.role,
            remark=request.remark,
            rate_limit=request.rate_limit
        )
        
        # Get user info
        async with get_db_connection() as conn:
            async with conn.cursor() as cursor:

                await cursor.execute(
                    "SELECT id, user_name, role, remark, status, created_at, rate_limit FROM api_users WHERE user_name = %s",
                    (request.user_name,)
                )
                row = await cursor.fetchone()
                if row:
                    columns = [col[0] for col in cursor.description]
                    user_data = dict(zip(columns, row))
                    user_data["api_key"] = api_key  # Return full key only once
                    
                    # Sync sys_user_resources
                    allowed_resources = request.allowed_resources or []
                    if allowed_resources and user_data["id"]:
                        values = [(user_data["id"], r) for r in allowed_resources]
                        await cursor.executemany(
                            "INSERT IGNORE INTO sys_user_resources (user_id, resource_key) VALUES (%s, %s)",
                            values
                        )
                        await conn.commit()
                        
                        # Add to response
                        user_data["allowed_resources"] = allowed_resources
                        
                    return user_data
                else:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="User created but failed to retrieve"
                    )
    except Exception as e:
        # Check for duplicate username
        if "Duplicate entry" in str(e) or "UNIQUE constraint" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.put("/users/{user_id}")

async def update_user(user_id: int, request: UpdateUserRequest, user: dict = Depends(require_permission("element:user:manage"))):
    """
    Update user role and permissions.
    Admin only.
    """
    update_fields = []
    params = []
    
    if request.role is not None:
        if request.role not in ["admin", "user"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role must be 'admin' or 'user'"
            )
        update_fields.append("role = %s")
        params.append(request.role)
    
    if request.remark is not None:
        update_fields.append("remark = %s")
        params.append(request.remark)
    
    if request.rate_limit is not None:
        update_fields.append("rate_limit = %s")
        params.append(request.rate_limit)
    
    if request.masking_strategy is not None:
        update_fields.append("masking_strategy = %s")
        params.append(request.masking_strategy)
    
    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    params.append(user_id)
    
    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            # Check if user exists
            await cursor.execute(
                "SELECT id FROM api_users WHERE id = %s",
                (user_id,)
            )
            if not await cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # Update user
            sql = f"UPDATE api_users SET {', '.join(update_fields)} WHERE id = %s"
            await cursor.execute(sql, tuple(params))
            await conn.commit()
            
            # Invalidate Cache
            from app.services.permission_service import PermissionService
            await PermissionService.invalidate_user_cache(user_id)
            
            # Update sys_user_resources if allowed_resources changed
            if request.allowed_resources is not None:
                allowed_resources = request.allowed_resources
                
                # Full replacement strategy
                await cursor.execute("DELETE FROM sys_user_resources WHERE user_id = %s", (user_id,))
                
                if allowed_resources:
                    values = [(user_id, r) for r in allowed_resources]
                    await cursor.executemany(
                        "INSERT IGNORE INTO sys_user_resources (user_id, resource_key) VALUES (%s, %s)",
                        values
                    )
                await conn.commit()

            # Update UI Permissions (Menus, Elements, Data Assets)
            if any(x is not None for x in [request.menus, request.elements, request.datasources, request.data_tables]):
                # 1. Clear existing direct permissions
                await cursor.execute(
                    "DELETE FROM sys_ui_permissions WHERE user_id = %s AND role_id IS NULL", 
                    (user_id,)
                )
                
                perm_values = []
                # 2. Add Menus
                if request.menus:
                    for m in request.menus: perm_values.append((user_id, 'menu', m))
                
                # 3. Add Elements
                if request.elements:
                    for e in request.elements: perm_values.append((user_id, 'element', e))

                # 4. Add Data Sources
                if request.datasources:
                    for d in request.datasources: perm_values.append((user_id, 'datasource', d))

                # 5. Add Data Tables
                if request.data_tables:
                    for t in request.data_tables: perm_values.append((user_id, 'data_table', t))

                if perm_values:
                    await cursor.executemany(
                        "INSERT INTO sys_ui_permissions (user_id, perm_type, perm_code) VALUES (%s, %s, %s)",
                        perm_values
                    )
                
                await conn.commit()
                # Clear permission cache
                from app.services.permission_service import PermissionService
                await PermissionService.invalidate_user_cache(user_id)

            # Update Roles (sys_user_role_relation)
            if request.role_ids is not None:
                await cursor.execute("DELETE FROM sys_user_role_relation WHERE user_id = %s", (user_id,))
                if request.role_ids:
                    role_values = [(user_id, rid) for rid in request.role_ids]
                    await cursor.executemany(
                        "INSERT INTO sys_user_role_relation (user_id, role_id) VALUES (%s, %s)",
                        role_values
                    )
                await conn.commit()
                from app.services.permission_service import PermissionService
                await PermissionService.invalidate_user_cache(user_id)





            # Get updated user
            await cursor.execute(
                "SELECT id, user_name, role, remark, status, created_at, updated_at, masking_strategy FROM api_users WHERE id = %s",
                (user_id,)
            )
            row = await cursor.fetchone()
            columns = [col[0] for col in cursor.description]
            item = dict(zip(columns, row))
            
            # Populate resources for response consistency
            await cursor.execute("SELECT resource_key FROM sys_user_resources WHERE user_id = %s", (user_id,))
            res_rows = await cursor.fetchall()
            current_resources = [r[0] for r in res_rows]
            
            item["allowed_resources"] = current_resources
            
            return item

@router.patch("/users/{user_id}/status")
async def update_user_status(user_id: int, request: UpdateStatusRequest, user: dict = Depends(require_permission("element:user:manage"))):
    """
    Enable or disable a user.
    Admin only. Cannot disable yourself.
    """
    # Prevent admin from disabling themselves
    current_user_id = user.get("user_id")
    # Convert both to int for comparison
    try:
        current_user_id = int(current_user_id)
    except (TypeError, ValueError):
        pass
    
    if user_id == current_user_id and request.status == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot disable yourself"
        )
    
    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            # Check if user exists
            await cursor.execute(
                "SELECT id FROM api_users WHERE id = %s",
                (user_id,)
            )
            if not await cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # Update status
            await cursor.execute(
                "UPDATE api_users SET status = %s WHERE id = %s",
                (request.status, user_id)
            )
            await conn.commit()
            
            return {"message": "User status updated successfully"}

@router.get("/api-key/{user_id}")
async def get_user_api_key_decrypted(user_id: int, user: dict = Depends(require_api_key)):
    """
    Get decrypted API Key for a user.
    Admin/Managers can view any user's key, regular users can only view their own.
    """
    current_user_id = user.get("user_id")
    current_role = user.get("role")
    
    # Convert to int for comparison
    try:
        uid_int = int(current_user_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user context")
    
    # Permission check: 
    # 1. Admin bypass
    # 2. User viewing own key
    # 3. Manager with element:user:manage permission
    has_manage_perm = "element:user:manage" in user.get("permissions", {}).get("elements", [])
    
    if current_role != "admin" and uid_int != user_id and not has_manage_perm:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own API Key"
        )
    
    # Get decrypted API Key
    api_key = await AuthService.get_decrypted_api_key(user_id)
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key not found for this user"
        )
    
    return {
        "user_id": user_id,
        "api_key": api_key
    }

@router.delete("/users/{user_id}")

async def delete_user(user_id: int, user: dict = Depends(require_permission("element:user:manage"))):
    """
    Delete a user.
    Admin only. Cannot delete yourself.
    """
    # Prevent admin from deleting themselves
    current_user_id = user.get("user_id")
    # Convert both to int for comparison
    try:
        current_user_id = int(current_user_id)
    except (TypeError, ValueError):
        pass
    
    if user_id == current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete yourself"
        )
    
    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            # Check if user exists
            await cursor.execute(
                "SELECT id, user_name FROM api_users WHERE id = %s",
                (user_id,)
            )
            user = await cursor.fetchone()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # Prevent deleting system admin
            if user[1] == "admin":
                 raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot delete system admin"
                )
            
            # Delete user
            await cursor.execute(
                "DELETE FROM api_users WHERE id = %s",
                (user_id,)
            )
            await conn.commit()
            
            return {"message": "User deleted successfully"}


@router.post("/users/{user_id}/password/reset")
async def reset_user_password(user_id: int, user: dict = Depends(require_permission("element:user:manage"))):
    """
    Reset user's API Key without changing user info.
    Admin only.
    """
    # Prevent admin from resetting their own key (optional restriction)
    current_user_id = user.get("user_id")
    try:
        current_user_id = int(current_user_id)
    except (TypeError, ValueError):
        pass
    
    # Optional: Prevent user from resetting their own key
    # if user_id == current_user_id:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Cannot reset your own API Key"
    #     )
    
    async with get_db_connection() as conn:
        async with conn.cursor() as cursor:
            # Check if user exists
            await cursor.execute(
                "SELECT id FROM api_users WHERE id = %s",
                (user_id,)
            )
            if not await cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
    # Reset the API Key
    new_api_key = await AuthService.reset_api_key(user_id)
    
    if not new_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset API Key"
        )
    
    return {
        "message": "API Key reset successfully",
        "user_id": user_id,
        "api_key": new_api_key
    }
