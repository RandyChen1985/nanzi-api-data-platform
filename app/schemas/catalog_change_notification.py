from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class CatalogChangeNotificationItem(BaseModel):
    id: int
    product_id: int
    product_key: str
    product_display_name: str
    resource_key: str
    resource_name: Optional[str] = None
    version_id: Optional[int] = None
    action_type: str
    change_summary: Optional[str] = None
    operator_name: Optional[str] = None
    is_read: bool = False
    created_at: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.strftime("%Y-%m-%d %H:%M:%S") if v else None}


class CatalogChangeNotificationListResponse(BaseModel):
    total: int
    unread: int
    items: List[CatalogChangeNotificationItem] = Field(default_factory=list)


class CatalogChangeNotificationMarkReadRequest(BaseModel):
    ids: Optional[List[int]] = None
    mark_all: bool = False
