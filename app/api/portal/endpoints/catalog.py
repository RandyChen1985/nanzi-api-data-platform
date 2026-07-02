from fastapi import APIRouter, Depends, HTTPException, Query, Request, Body
from typing import List, Optional, Union
from datetime import datetime

from fastapi.responses import StreamingResponse

from app.core.dependencies import require_api_key, require_admin, require_permission
from app.schemas.catalog import (
    ProductListItem,
    ProductDetail,
    ProductUpdateRequest,
    PublishFromResourceRequest,
    DomainStat,
    PanoramaResponse,
    AccessRequestCreate,
    AccessRequestHandle,
    AccessRequestItem,
    BatchPublishResult,
    BatchPublishFromResourcesRequest,
    BatchAssignOwnerRequest,
    BatchAssignOwnerResult,
    PaginatedProductList,
    UnpublishRequest,
    RevokeAccessRequest,
    AccessHoldersResponse,
    CatalogSettingsResponse,
    CatalogSettingsUpdate,
    ProductResourcesUpdate,
    RedundantProductItem,
    ArchiveRedundantResult,
    SyncAccessResult,
)
from app.schemas.catalog_change_notification import (
    CatalogChangeNotificationListResponse,
    CatalogChangeNotificationMarkReadRequest,
)
from app.schemas.resource_version import ProductLinkedResourceVersionsResponse
from app.services.catalog_service import CatalogService, STATUS_DRAFT, REQUEST_PENDING
from app.services.catalog_change_notification_service import CatalogChangeNotificationService
from app.api.portal.endpoints.dashboard import is_admin

router = APIRouter()


def _can_view_panorama(user: dict) -> bool:
    if is_admin(user):
        return True
    menus = user.get("permissions", {}).get("menus", [])
    return "menu:asset-panorama" in menus


def _can_publish(user: dict) -> bool:
    if is_admin(user):
        return True
    perms = user.get("permissions", {}).get("elements", [])
    return "element:catalog:publish" in perms or "element:resource:edit" in perms


def _can_export(user: dict) -> bool:
    if is_admin(user):
        return True
    menus = user.get("permissions", {}).get("menus", [])
    perms = user.get("permissions", {}).get("elements", [])
    return "menu:asset-panorama" in menus or "element:catalog:manage" in perms


def _can_manage_catalog(user: dict) -> bool:
    if is_admin(user):
        return True
    return "element:catalog:manage" in user.get("permissions", {}).get("elements", [])


@router.get("/products", response_model=Union[List[ProductListItem], PaginatedProductList])
async def list_products(
    domain: Optional[str] = None,
    q: Optional[str] = Query(None, description="搜索关键词"),
    sort: str = Query("calls", description="排序: calls | newest | name | pending"),
    only_accessible: bool = False,
    only_no_access: bool = False,
    mine_only: bool = False,
    include_draft: bool = False,
    page: Optional[int] = Query(None, ge=1, description="页码，传入则返回分页结构"),
    page_size: int = Query(24, ge=1, le=100),
    user: dict = Depends(require_api_key),
):
    """数据产品目录列表（已发布产品全员可见元数据）"""
    return await CatalogService.list_products(
        user,
        domain=domain,
        q=q,
        sort=sort,
        only_accessible=only_accessible,
        only_no_access=only_no_access,
        mine_only=mine_only,
        include_draft=include_draft and is_admin(user),
        page=page,
        page_size=page_size,
    )


@router.get("/products/mine-summary")
async def get_mine_summary(user: dict = Depends(require_api_key)):
    """当前用户负责的产品数与待审批申请数"""
    return await CatalogService.get_mine_summary(user)


@router.get("/products/export")
async def export_products(user: dict = Depends(require_api_key)):
    """导出已发布产品清单 CSV"""
    if not _can_export(user):
        raise HTTPException(status_code=403, detail="无导出权限")
    content = await CatalogService.export_products_csv(user)
    filename = f"catalog_products_{datetime.now().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/products/sections")
async def get_product_sections(user: dict = Depends(require_api_key)):
    """热门 / 最新 / 精选分区"""
    return await CatalogService.get_sections(user)


@router.get("/domains", response_model=List[DomainStat])
async def list_domains(user: dict = Depends(require_api_key)):
    return await CatalogService.list_domains(user)


@router.post("/products/publish-from-resource")
async def publish_from_resource(
    request_in: Request,
    body: PublishFromResourceRequest,
    user: dict = Depends(require_api_key),
):
    request_in.state.action_type = "CATALOG_PUBLISH"
    if not _can_publish(user):
        raise HTTPException(status_code=403, detail="无发布权限")
    try:
        result = await CatalogService.upsert_from_resource(
            body.resource_key,
            user=user,
            display_name=body.display_name,
            summary=body.summary,
            domain=body.domain,
            owner_user_id=body.owner_user_id,
            publish=body.publish,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/products/batch-publish", response_model=BatchPublishResult)
async def batch_publish_all_drafts(
    request_in: Request,
    user: dict = Depends(require_admin),
):
    """批量发布目录中全部草稿产品（管理员）"""
    request_in.state.action_type = "CATALOG_BATCH_PUBLISH"
    return await CatalogService.batch_publish_drafts()


@router.post("/products/batch-publish-from-resources", response_model=BatchPublishResult)
async def batch_publish_from_resources(
    request_in: Request,
    body: BatchPublishFromResourcesRequest,
    user: dict = Depends(require_api_key),
):
    """批量将所选资源发布到目录（未进目录 / 草稿 / 已下架）"""
    request_in.state.action_type = "CATALOG_BATCH_PUBLISH"
    if not _can_publish(user):
        raise HTTPException(status_code=403, detail="无发布权限")
    try:
        return await CatalogService.batch_publish_from_resources(body.resource_keys, user=user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/assign-owner-users")
async def list_assign_owner_users(user: dict = Depends(require_api_key)):
    if not _can_manage_catalog(user):
        raise HTTPException(status_code=403, detail="无权限")
    return await CatalogService.list_active_users()


@router.get("/products/without-owner-count")
async def count_products_without_owner(user: dict = Depends(require_api_key)):
    if not _can_manage_catalog(user):
        raise HTTPException(status_code=403, detail="无权限")
    return {"count": await CatalogService.count_products_without_owner()}


@router.post("/products/batch-assign-owner", response_model=BatchAssignOwnerResult)
async def batch_assign_owner(
    request_in: Request,
    body: BatchAssignOwnerRequest,
    user: dict = Depends(require_api_key),
):
    request_in.state.action_type = "CATALOG_BATCH_ASSIGN_OWNER"
    if not _can_manage_catalog(user):
        raise HTTPException(status_code=403, detail="无批量指定负责人权限")
    try:
        return await CatalogService.batch_assign_owner(
            user,
            body.owner_user_id,
            product_keys=body.product_keys,
            only_without_owner=body.only_without_owner,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/products/redundant", response_model=List[RedundantProductItem])
async def list_redundant_products(user: dict = Depends(require_api_key)):
    """列出因 API 合并产生的冗余产品（主产品外仍单独存在的产品记录）"""
    return await CatalogService.list_redundant_products(user)


@router.get("/products/{product_key}/edit-meta")
async def get_product_edit_meta(product_key: str, user: dict = Depends(require_api_key)):
    try:
        return await CatalogService.get_edit_meta(user, product_key)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get(
    "/products/{product_key}/linked-resource-versions",
    response_model=ProductLinkedResourceVersionsResponse,
)
async def get_product_linked_resource_versions(
    product_key: str,
    keys: Optional[str] = Query(None, description="逗号分隔的 resource_key，默认取产品已关联资源"),
    limit: int = Query(5, ge=1, le=20),
    user: dict = Depends(require_api_key),
):
    resource_keys = [k.strip() for k in keys.split(",") if k.strip()] if keys else None
    try:
        return await CatalogService.get_linked_resource_versions(
            user, product_key, resource_keys=resource_keys, limit=limit
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/products/{product_key}", response_model=ProductDetail)
async def get_product_detail(product_key: str, user: dict = Depends(require_api_key)):
    product = await CatalogService.get_product(product_key, user)
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在或未发布")
    return product


@router.put("/products/{product_key}")
async def update_product(
    request_in: Request,
    product_key: str,
    body: ProductUpdateRequest,
    user: dict = Depends(require_api_key),
):
    request_in.state.action_type = "CATALOG_PRODUCT_UPDATE"
    if not await CatalogService.can_edit_product(user, product_key):
        raise HTTPException(status_code=403, detail="无产品编辑权限")
    data = body.model_dump(exclude_unset=True)
    perms = user.get("permissions", {}).get("elements", [])
    can_manage_catalog = user.get("role") == "admin" or "element:catalog:manage" in perms
    if not can_manage_catalog:
        data.pop("featured", None)
    ok = await CatalogService.update_product(product_key, data)
    if not ok:
        raise HTTPException(status_code=404, detail="产品不存在或无变更")
    return {"success": True}


@router.put("/products/{product_key}/resources")
async def update_product_resources(
    request_in: Request,
    product_key: str,
    body: ProductResourcesUpdate,
    user: dict = Depends(require_api_key),
):
    request_in.state.action_type = "CATALOG_PRODUCT_UPDATE"
    if not await CatalogService.can_edit_product(user, product_key):
        raise HTTPException(status_code=403, detail="无产品编辑权限")
    try:
        resources = [r.model_dump() for r in body.resources]
        await CatalogService.update_product_resources(product_key, resources)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True}


@router.get("/settings", response_model=CatalogSettingsResponse)
async def get_catalog_settings(user: dict = Depends(require_permission("element:config:save"))):
    return await CatalogService.get_catalog_settings()


@router.put("/settings", response_model=CatalogSettingsResponse)
async def update_catalog_settings(
    body: CatalogSettingsUpdate,
    user: dict = Depends(require_permission("element:config:save")),
):
    try:
        await CatalogService.update_catalog_settings(
            default_owner_strategy=body.default_owner_strategy,
            group_owner_map=body.group_owner_map,
            notify_resource_change_enabled=body.notify_resource_change_enabled,
            notify_resource_change_webhook_url=body.notify_resource_change_webhook_url,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await CatalogService.get_catalog_settings()


@router.post("/products/{product_key}/publish")
async def publish_product(
    request_in: Request,
    product_key: str,
    user: dict = Depends(require_admin),
):
    request_in.state.action_type = "CATALOG_PUBLISH"
    try:
        ok = await CatalogService.publish_product(product_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not ok:
        raise HTTPException(status_code=404, detail="产品不存在")
    return {"success": True}


@router.get("/products/{product_key}/unpublish-preview", response_model=AccessHoldersResponse)
async def unpublish_preview(product_key: str, user: dict = Depends(require_admin)):
    try:
        return await CatalogService.get_product_access_holders(product_key)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/products/{product_key}/access-holders", response_model=AccessHoldersResponse)
async def list_access_holders(product_key: str, user: dict = Depends(require_api_key)):
    if not await CatalogService.can_revoke_access(user, product_key):
        raise HTTPException(status_code=403, detail="无权限查看")
    try:
        return await CatalogService.get_product_access_holders(product_key)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/products/{product_key}/revoke-access")
async def revoke_product_access(
    request_in: Request,
    product_key: str,
    body: RevokeAccessRequest,
    user: dict = Depends(require_api_key),
):
    request_in.state.action_type = "CATALOG_ACCESS_REVOKE"
    try:
        removed = await CatalogService.revoke_product_access(
            user,
            product_key,
            user_id=body.user_id,
            revoke_all=body.revoke_all,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "removed": removed}


@router.post("/products/{product_key}/unpublish")
async def unpublish_product(
    request_in: Request,
    product_key: str,
    body: UnpublishRequest = Body(default_factory=UnpublishRequest),
    user: dict = Depends(require_admin),
):
    request_in.state.action_type = "CATALOG_UNPUBLISH"
    ok = await CatalogService.unpublish_product(
        product_key, revoke_permissions=body.revoke_permissions
    )
    if not ok:
        raise HTTPException(status_code=404, detail="产品不存在")
    return {"success": True}


@router.get("/products/{product_key}/resource-conflicts", response_model=List[RedundantProductItem])
async def check_resource_conflicts(
    product_key: str,
    keys: str = Query(..., description="逗号分隔的 resource_key"),
    user: dict = Depends(require_api_key),
):
    if not await CatalogService.can_edit_product(user, product_key):
        raise HTTPException(status_code=403, detail="无编辑权限")
    resource_keys = [k.strip() for k in keys.split(",") if k.strip()]
    return await CatalogService.check_resource_conflicts(
        resource_keys, host_product_key=product_key
    )


@router.post("/products/{product_key}/archive-redundant", response_model=ArchiveRedundantResult)
async def archive_redundant_product(
    request_in: Request,
    product_key: str,
    body: UnpublishRequest = Body(default=UnpublishRequest()),
    user: dict = Depends(require_api_key),
):
    request_in.state.action_type = "CATALOG_PRODUCT_ARCHIVE"
    try:
        return await CatalogService.archive_redundant_product(
            user, product_key, revoke_permissions=body.revoke_permissions
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/products/{product_key}/sync-access", response_model=SyncAccessResult)
async def sync_product_access(
    request_in: Request,
    product_key: str,
    user: dict = Depends(require_api_key),
):
    """已通过审批后补同步 API 资源权限（写入 sys_user_resources 并刷新缓存）"""
    request_in.state.action_type = "CATALOG_ACCESS_SYNC"
    try:
        return await CatalogService.sync_user_product_access(user, product_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/products/{product_key}/access-request")
async def create_access_request(
    request_in: Request,
    product_key: str,
    body: AccessRequestCreate,
    user: dict = Depends(require_api_key),
):
    request_in.state.action_type = "CATALOG_ACCESS_REQUEST"
    try:
        return await CatalogService.create_access_request(user, product_key, body.message)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/access-requests/mine", response_model=List[AccessRequestItem])
async def list_my_access_requests(
    status: Optional[int] = Query(None, description="0待审批 1已通过 2已拒绝 3已收回"),
    user: dict = Depends(require_api_key),
):
    """当前用户提交的目录权限申请"""
    return await CatalogService.list_my_access_requests(user, status=status)


@router.get("/access-requests/mine/status-counts")
async def my_access_request_status_counts(user: dict = Depends(require_api_key)):
    """我的申请页各 Tab 数量统计"""
    return await CatalogService.count_my_access_requests_by_status(user)


@router.get("/access-requests", response_model=List[AccessRequestItem])
async def list_access_requests(
    status: Optional[int] = Query(None, description="0待审批 1已通过 2已拒绝，不传=全部"),
    user: dict = Depends(require_api_key),
):
    return await CatalogService.list_access_requests(user, status=status)


@router.get("/access-requests/pending-count")
async def pending_request_count(user: dict = Depends(require_api_key)):
    count = await CatalogService.count_pending_requests(user)
    summary = await CatalogService.get_mine_summary(user)
    can_access = CatalogService.can_access_catalog_requests(
        user, owned_products=summary["owned_products"]
    )
    change_unread = await CatalogChangeNotificationService.count_unread(int(user["user_id"]))
    return {
        "count": count,
        "owned_products": summary["owned_products"],
        "show_requests_menu": can_access,
        "can_access_requests": can_access,
        "change_notification_unread": change_unread,
        "show_change_notifications_menu": summary["owned_products"] > 0,
    }


@router.get("/access-requests/status-counts")
async def access_request_status_counts(user: dict = Depends(require_api_key)):
    """审批页各 Tab 数量统计"""
    summary = await CatalogService.get_mine_summary(user)
    if not CatalogService.can_access_catalog_requests(
        user, owned_products=summary["owned_products"]
    ):
        raise HTTPException(status_code=403, detail="无权查看权限审批")
    return await CatalogService.count_access_requests_by_status(user)


@router.post("/access-requests/{request_id}/approve")
async def approve_access_request(
    request_in: Request,
    request_id: int,
    body: AccessRequestHandle,
    user: dict = Depends(require_api_key),
):
    request_in.state.action_type = "CATALOG_ACCESS_APPROVE"
    try:
        ok = await CatalogService.approve_access_request(request_id, user, body.remark)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not ok:
        raise HTTPException(status_code=404, detail="申请不存在或已处理")
    return {"success": True}


@router.post("/access-requests/{request_id}/reject")
async def reject_access_request(
    request_in: Request,
    request_id: int,
    body: AccessRequestHandle,
    user: dict = Depends(require_api_key),
):
    request_in.state.action_type = "CATALOG_ACCESS_REJECT"
    try:
        ok = await CatalogService.reject_access_request(request_id, user, body.remark)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    if not ok:
        raise HTTPException(status_code=404, detail="申请不存在或已处理")
    return {"success": True}


@router.post("/access-requests/{request_id}/revoke-access")
async def revoke_access_by_request(
    request_in: Request,
    request_id: int,
    user: dict = Depends(require_api_key),
):
    request_in.state.action_type = "CATALOG_ACCESS_REVOKE"
    try:
        removed = await CatalogService.revoke_access_by_request(request_id, user)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "removed": removed}


@router.get("/change-notifications", response_model=CatalogChangeNotificationListResponse)
async def list_change_notifications(
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: dict = Depends(require_api_key),
):
    summary = await CatalogService.get_mine_summary(user)
    if summary["owned_products"] <= 0 and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="您不是任何数据产品的负责人")
    return await CatalogChangeNotificationService.list_notifications(
        int(user["user_id"]),
        unread_only=unread_only,
        page=page,
        size=size,
    )


@router.post("/change-notifications/mark-read")
async def mark_change_notifications_read(
    body: CatalogChangeNotificationMarkReadRequest,
    user: dict = Depends(require_api_key),
):
    if not body.mark_all and not body.ids:
        raise HTTPException(status_code=400, detail="请指定 ids 或 mark_all")
    affected = await CatalogChangeNotificationService.mark_read(
        int(user["user_id"]),
        ids=body.ids,
        mark_all=body.mark_all,
    )
    unread = await CatalogChangeNotificationService.count_unread(int(user["user_id"]))
    return {"success": True, "marked": affected, "unread": unread}


@router.get("/panorama", response_model=PanoramaResponse)
async def get_asset_panorama(
    days: int = Query(30, ge=1, le=90),
    user: dict = Depends(require_api_key),
):
    if not _can_view_panorama(user):
        raise HTTPException(status_code=403, detail="无资产全景查看权限")
    return await CatalogService.get_panorama(days)


@router.get("/status-map")
async def get_catalog_status_map(user: dict = Depends(require_api_key)):
    """资源管理页用：查询各资源对应的目录发布状态"""
    return await CatalogService.get_product_status_map()
