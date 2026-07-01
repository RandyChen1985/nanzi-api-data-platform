from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from datetime import datetime
from app.schemas.resource import FieldConfig


class ProductResourceInfo(BaseModel):
    resource_key: str
    resource_name: Optional[str] = None
    resource_mode: Optional[str] = None
    resource_group: Optional[str] = None
    data_source: Optional[str] = None
    fields_config: List[FieldConfig] = Field(default_factory=list)
    allowed_filters: List[FieldConfig] = Field(default_factory=list)
    is_primary: bool = True


class ProductListItem(BaseModel):
    id: int
    product_key: str
    display_name: str
    summary: Optional[str] = None
    domain: str
    tags: List[str] = Field(default_factory=list)
    status: int
    featured: bool = False
    owner_name: Optional[str] = None
    owner_user_id: Optional[int] = None
    primary_resource_key: Optional[str] = None
    data_source: Optional[str] = None
    resource_mode: Optional[str] = None
    health_score: Optional[int] = None
    calls_7d: int = 0
    has_access: bool = False
    resource_group: Optional[str] = None
    pending_requests: int = 0
    published_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        json_encoders = {datetime: lambda v: v.strftime("%Y-%m-%d %H:%M:%S") if v else None}


class ProductDetail(ProductListItem):
    description: Optional[str] = None
    resources: List[ProductResourceInfo] = Field(default_factory=list)
    dataset_name: Optional[str] = None
    dataset_id: Optional[int] = None
    calls_trend: List[Dict[str, Any]] = Field(default_factory=list)
    can_edit: bool = False
    can_manage_access: bool = False
    access_request_status: Optional[str] = None


class PaginatedProductList(BaseModel):
    items: List[ProductListItem]
    total: int
    page: int
    page_size: int


class UnpublishRequest(BaseModel):
    revoke_permissions: bool = False


class RevokeAccessRequest(BaseModel):
    user_id: Optional[int] = None
    revoke_all: bool = False


class AccessHolderItem(BaseModel):
    user_id: int
    user_name: str
    remark: Optional[str] = None
    granted_resources: int = 0


class AccessHoldersResponse(BaseModel):
    count: int
    holders: List[AccessHolderItem] = Field(default_factory=list)


class ProductUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    domain: Optional[str] = None
    tags: Optional[List[str]] = None
    owner_user_id: Optional[int] = None
    dataset_id: Optional[int] = None
    featured: Optional[bool] = None


class PublishFromResourceRequest(BaseModel):
    resource_key: str
    display_name: Optional[str] = None
    summary: Optional[str] = None
    domain: Optional[str] = None
    owner_user_id: Optional[int] = None
    publish: bool = False


class AccessRequestCreate(BaseModel):
    message: Optional[str] = Field(None, max_length=500)


class AccessRequestHandle(BaseModel):
    remark: Optional[str] = Field(None, max_length=255)


class AccessRequestItem(BaseModel):
    id: int
    product_key: str
    product_name: Optional[str] = None
    user_id: int
    user_name: str
    message: Optional[str] = None
    status: int
    handler_name: Optional[str] = None
    handle_remark: Optional[str] = None
    handled_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    owner_user_id: Optional[int] = None
    access_active: Optional[bool] = None
    primary_resource_key: Optional[str] = None
    resource_group: Optional[str] = None


class BatchPublishResult(BaseModel):
    published: int
    skipped: List[Dict[str, str]] = Field(default_factory=list)
    total: int = 0


class BatchAssignOwnerRequest(BaseModel):
    owner_user_id: int
    product_keys: Optional[List[str]] = None
    only_without_owner: bool = True


class BatchAssignOwnerResult(BaseModel):
    updated: int
    skipped: int = 0
    total: int = 0


class CatalogSettingsResponse(BaseModel):
    default_owner_strategy: str
    group_owner_map: Dict[str, int] = Field(default_factory=dict)
    notify_resource_change_enabled: bool = True
    notify_resource_change_webhook_url: str = ""


class CatalogSettingsUpdate(BaseModel):
    default_owner_strategy: str = "publisher"
    group_owner_map: Dict[str, int] = Field(default_factory=dict)
    notify_resource_change_enabled: Optional[bool] = None
    notify_resource_change_webhook_url: Optional[str] = None


class ProductResourceLink(BaseModel):
    resource_key: str
    is_primary: bool = False


class ProductResourcesUpdate(BaseModel):
    resources: List[ProductResourceLink]


class RedundantProductItem(BaseModel):
    product_key: str
    display_name: str
    status: int
    owner_user_id: Optional[int] = None
    owner_name: Optional[str] = None
    duplicate_resource_key: str
    host_product_key: str
    host_display_name: str


class ArchiveRedundantResult(BaseModel):
    archived: bool
    product_key: str
    host_product_key: str


class SyncAccessResult(BaseModel):
    has_access: bool
    resource_keys: List[str] = Field(default_factory=list)
    granted_count: int = 0
    required_count: int = 0


class DomainStat(BaseModel):
    domain: str
    count: int


class PanoramaAlerts(BaseModel):
    zero_call_products: List[ProductListItem] = Field(default_factory=list)
    low_health_products: List[ProductListItem] = Field(default_factory=list)
    incomplete_products: List[ProductListItem] = Field(default_factory=list)
    new_this_month: int = 0


class PanoramaResponse(BaseModel):
    period_days: int
    published_count: int
    domain_count: int
    datasource_types: Dict[str, int] = Field(default_factory=dict)
    total_calls: int
    active_consumers: int
    domain_distribution: List[DomainStat] = Field(default_factory=list)
    calls_trend: List[Dict[str, Any]] = Field(default_factory=list)
    top_products: List[ProductListItem] = Field(default_factory=list)
    health_summary: Dict[str, int] = Field(default_factory=dict)
    alerts: PanoramaAlerts
