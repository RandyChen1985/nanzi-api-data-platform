from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from datetime import datetime


class ResourceVersionSummary(BaseModel):
    id: int
    resource_key: str
    version_no: int
    action_type: str
    change_summary: Optional[str] = None
    operator_user_id: Optional[int] = None
    operator_name: Optional[str] = None
    created_at: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.strftime("%Y-%m-%d %H:%M:%S")
        }


class ResourceVersionDetail(ResourceVersionSummary):
    snapshot: Dict[str, Any]


class ResourceVersionDiffItem(BaseModel):
    field: str
    label: str
    current_value: Any = None
    version_value: Any = None


class ResourceVersionDiffResponse(BaseModel):
    resource_key: str
    version_id: int
    version_no: int
    compare_target: str = Field("current", description="current or previous")
    items: List[ResourceVersionDiffItem]


class ResourceVersionListResponse(BaseModel):
    total: int
    items: List[ResourceVersionSummary]


class LinkedResourceVersionGroup(BaseModel):
    resource_key: str
    resource_name: Optional[str] = None
    is_primary: bool = False
    total_versions: int = 0
    recent_versions: List[ResourceVersionSummary] = Field(default_factory=list)


class ProductLinkedResourceVersionsResponse(BaseModel):
    product_key: str
    resources: List[LinkedResourceVersionGroup] = Field(default_factory=list)
