from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.v1.schemas.data import BaseResponse, COMMON_ERROR_RESPONSES
from app.core.dependencies import require_api_key, check_rate_limit
from app.services.meta_service import MetaService
from app.services.mcp_settings_service import McpSettingsService

router = APIRouter()


class AccessibleResourceItem(BaseModel):
    resource_key: str
    resource_name: str
    resource_group: str
    data_source: str
    resource_mode: Optional[str] = None
    remarks: Optional[str] = None
    allowed_filters: List[Any] = Field(default_factory=list)
    default_sort: Optional[str] = None
    status: int = 1


class AccessibleResourceListData(BaseModel):
    items: List[AccessibleResourceItem]
    total: int


@router.get(
    "/resources",
    response_model=BaseResponse,
    summary="列出当前凭证可访问的数据资源",
    responses=COMMON_ERROR_RESPONSES,
)
async def list_accessible_resources(
    user: Dict = Depends(require_api_key),
    _rate_limit: None = Depends(check_rate_limit),
):
    """
    返回当前 API Key 拥有 RBAC 权限且处于启用状态的资源列表。
    供 MCP、智能体或集成方发现可调用的 resource_key。
    """
    all_resources = await MetaService.list_resources()
    active = [r for r in all_resources if r.status == 1]

    if user.get("role") == "admin":
        allowed_keys = {r.resource_key for r in active}
    else:
        allowed_keys = set(user.get("permissions", {}).get("resources", []))

    items: List[AccessibleResourceItem] = []
    for r in active:
        if r.resource_key not in allowed_keys:
            continue
        items.append(
            AccessibleResourceItem(
                resource_key=r.resource_key,
                resource_name=r.resource_name,
                resource_group=r.resource_group,
                data_source=r.data_source,
                resource_mode=r.resource_mode,
                remarks=r.remarks,
                allowed_filters=r.allowed_filters or [],
                default_sort=r.default_sort,
                status=r.status,
            )
        )

    items.sort(key=lambda x: (x.resource_group or "", x.resource_key))
    return BaseResponse(
        data=AccessibleResourceListData(items=items, total=len(items)).model_dump()
    )


@router.get("/mcp/status", summary="MCP Server 启用状态", include_in_schema=True)
async def mcp_status(request: Request):
    """公开状态探针：客户端（含 stdio MCP）可判断是否允许连接，并获取当前访问根地址。"""
    settings = await McpSettingsService.get_settings(str(request.base_url).rstrip("/"))
    return {
        "enabled": settings["enabled"],
        "sse_path": settings["sse_path"],
        "sse_url": settings.get("sse_url") or "",
        "public_base_url": settings.get("public_base_url") or "",
        "stdio_command": settings["stdio_command"],
        "message": "MCP Server 已启用" if settings["enabled"] else "MCP Server 未启用，请在系统配置中开启",
    }
