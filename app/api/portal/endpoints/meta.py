from fastapi import APIRouter, Depends, HTTPException, Body, Request
from typing import List
from app.schemas.resource import ResourceCreate, ResourceUpdate, ResourceResponse
from app.schemas.introspection import TableListResponse, ColumnListResponse, ColumnIntrospectRequest
from app.schemas.resource_version import (
    ResourceVersionDetail,
    ResourceVersionDiffResponse,
    ResourceVersionListResponse,
)
from app.services.meta_service import MetaService
from app.services.resource_version_service import ResourceVersionService
from app.core.dependencies import require_admin, require_api_key, require_permission
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/resources", response_model=List[ResourceResponse])
async def list_resources(
    user: dict = Depends(require_api_key)
):
    """
    List all resource configurations.
    """
    resources = await MetaService.list_resources()
    return resources

@router.post("/resources", response_model=ResourceResponse)
async def create_resource(
    request_in: Request,
    resource: ResourceCreate,
    user: dict = Depends(require_api_key)
):
    """
    Create a new resource configuration.
    """
    request_in.state.action_type = 'META_RESOURCE_CREATE'
    try:
        # Check if exists
        existing = await MetaService.get_config(resource.resource_key)
        if existing:
            raise HTTPException(status_code=400, detail=f"Resource {resource.resource_key} already exists")
            
        new_resource = await MetaService.create_resource(resource, operator=user)
        return new_resource
    except Exception as e:
        logger.error(f"Failed to create resource: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/resources/{resource_key}", response_model=ResourceResponse)
async def update_resource(
    request_in: Request,
    resource_key: str,
    update_data: ResourceUpdate,
    user: dict = Depends(require_api_key)
):
    """
    Update a resource configuration.
    """
    request_in.state.action_type = 'META_RESOURCE_UPDATE'
    try:
        existing = await MetaService.get_config(resource_key)
        if not existing:
            raise HTTPException(status_code=404, detail="Resource not found")
            
        updated = await MetaService.update_resource(resource_key, update_data, operator=user)
        return updated
    except Exception as e:
        logger.error(f"Failed to update resource: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/resources/{resource_key}", response_model=dict)
async def delete_resource(
    request_in: Request,
    resource_key: str,
    user: dict = Depends(require_api_key)
):
    """
    Delete a resource configuration.
    """
    request_in.state.action_type = 'META_RESOURCE_DELETE'
    try:
        success = await MetaService.delete_resource(resource_key)
        if not success:
            raise HTTPException(status_code=404, detail="Resource not found")
        return {"deleted_key": resource_key, "message": "Resource deleted"}
    except Exception as e:
        logger.error(f"Failed to delete resource: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/resources/{resource_key}/versions", response_model=ResourceVersionListResponse)
async def list_resource_versions(
    resource_key: str,
    page: int = 1,
    size: int = 20,
    user: dict = Depends(require_api_key),
):
    existing = await MetaService.get_config(resource_key)
    if not existing:
        raise HTTPException(status_code=404, detail="Resource not found")
    return await ResourceVersionService.list_versions(resource_key, page=page, size=size)


@router.get("/resources/{resource_key}/versions/{version_id}", response_model=ResourceVersionDetail)
async def get_resource_version(
    resource_key: str,
    version_id: int,
    user: dict = Depends(require_api_key),
):
    version = await ResourceVersionService.get_version(version_id)
    if not version or version.resource_key != resource_key:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


@router.get(
    "/resources/{resource_key}/versions/{version_id}/diff",
    response_model=ResourceVersionDiffResponse,
)
async def diff_resource_version(
    resource_key: str,
    version_id: int,
    compare_target: str = "current",
    user: dict = Depends(require_api_key),
):
    if compare_target not in ("current", "previous"):
        raise HTTPException(status_code=400, detail="compare_target must be current or previous")

    current = await MetaService.get_config(resource_key)
    if not current:
        raise HTTPException(status_code=404, detail="Resource not found")

    diff = await ResourceVersionService.diff_version(
        resource_key, version_id, current, compare_target=compare_target
    )
    if not diff:
        raise HTTPException(status_code=404, detail="Version not found")
    return diff


@router.post("/resources/{resource_key}/versions/{version_id}/rollback", response_model=ResourceResponse)
async def rollback_resource_version(
    request_in: Request,
    resource_key: str,
    version_id: int,
    user: dict = Depends(require_permission("element:resource:edit")),
):
    request_in.state.action_type = "META_RESOURCE_ROLLBACK"
    existing = await MetaService.get_config(resource_key)
    if not existing:
        raise HTTPException(status_code=404, detail="Resource not found")

    rolled_back = await MetaService.rollback_resource(resource_key, version_id, operator=user)
    if not rolled_back:
        raise HTTPException(status_code=404, detail="Version not found")
    return rolled_back

@router.post("/datasource/tables", response_model=TableListResponse)
async def list_tables(
    data_source: str = Body(..., embed=True),
    user: dict = Depends(require_api_key)
):
    """
    List tables in the data source.
    Filtering based on user permissions for non-admin users.
    """
    try:
        # 1. Fetch all tables from data source
        all_tables = await MetaService.get_tables(data_source)
        all_tables = await MetaService.enrich_tables_with_metadata(data_source, all_tables)
        
        # 2. Admin Bypass
        if user.get("role") == "admin":
            return {"tables": all_tables}
            
        # 3. Regular User Filtering
        from app.services.permission_service import PermissionService
        user_perms = await PermissionService.get_user_permissions(int(user["user_id"]))
        perms = user_perms.permissions
        
        # Check DS Access first
        if f"ds:{data_source}" not in perms.datasources:
             return {"tables": []}
             
        # Check Table Access
        # Policy: ALL (*) = All, Specific = Whitelist, Empty = None
        if f"ds:{data_source}:table:*" in perms.data_tables:
            return {"tables": all_tables}
            
        # Whitelist filtering
        allowed_tables = [p.split(":table:")[-1] for p in perms.data_tables if p.startswith(f"ds:{data_source}:table:")]
        if not allowed_tables:
            return {"tables": []}
            
        # all_tables is now List[Dict] with 'name' and 'type' keys
        filtered = [t for t in all_tables if t['name'].lower() in [at.lower() for at in allowed_tables]]
        return {"tables": filtered}
        
    except Exception as e:
        logger.error(f"Failed to list tables: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/datasource/columns", response_model=ColumnListResponse)
async def list_columns(
    request: ColumnIntrospectRequest,
    user: dict = Depends(require_api_key)
):
    """
    List columns for a table or custom SQL.
    """
    try:
        columns = await MetaService.get_columns(
            data_source=request.data_source,
            table_name=request.table_name,
            custom_sql=request.custom_sql,
            params=request.params
        )
        columns = await MetaService.enrich_columns_with_metadata(
            request.data_source, request.table_name, columns
        )
        return {"columns": columns}
    except Exception as e:
        logger.error(f"Failed to introspect columns: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/resources/{resource_key}/test")
async def test_resource(
    resource_key: str,
    request: Request,
    user: dict = Depends(require_api_key)
):
    """
    Test execution endpoint. 
    Accessible to anyone with access to this resource (to support read-only mode testing).
    """
    from app.core.dependencies import verify_resource_access
    # 1. Check if user has permission for this resource
    await verify_resource_access(user, resource_key)

    from app.services.data_adapter.models import LogicalQuery
    from app.services.data_adapter.factory import get_adapter
    
    # 2. Fetch Config
    config = await MetaService.get_config(resource_key)
    if not config:
        raise HTTPException(status_code=404, detail="Resource not found")

    # 2. Parse Filters (Mirroring universal.py logic)
    reserved_params = {"page", "size", "sort_by", "sort_order"}
    filters = []
    
    import json
    for k, v in request.query_params.multi_items():
        if k in reserved_params: continue
        
        # Simple parsing for testing
        if isinstance(v, str) and v.startswith('[') and v.endswith(']'):
            try:
                val = json.loads(v)
                if isinstance(val, list):
                    filters.append((k, "IN", val))
                    continue
            except: pass
        filters.append((k, "=", v))

    # 3. Construct Query
    query = LogicalQuery(
        resource=resource_key,
        page=int(request.query_params.get("page", 1)),
        size=int(request.query_params.get("size", 20)),
        filters=filters,
        sort_by=request.query_params.get("sort_by"),
        sort_order=request.query_params.get("sort_order", "DESC").upper()
    )

    # 4. Execute
    adapter = await get_adapter(config.data_source)
    result = await adapter.execute(query)
    
    # 5. Apply Data Masking
    from app.services.masking_service import MaskingService
    if await MaskingService.should_mask(user): # Default unmask=False for test
        result.items = await MaskingService.mask_recursive(result.items)
    
    return {"code": 200, "message": "success", "data": result}
