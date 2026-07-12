from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, validator
from app.schemas.resource import validate_user_resource_group

class PreviewRequest(BaseModel):
    source_id: int
    sql: str
    params: Optional[Dict[str, Any]] = None
    limit: int = 100
    offset: int = 0
    include_total: bool = False
    unmask: bool = False
    skip_risk_check: bool = False

class ExplainRequest(BaseModel):
    source_id: int
    sql: str
    params: Optional[Dict[str, Any]] = None

class RiskCheckRequest(BaseModel):
    sql: str
    source_id: Optional[int] = None

class ExportRequest(BaseModel):
    source_id: int
    sql: str
    params: Optional[Dict[str, Any]] = None
    format: str = "csv"  # csv | xlsx (xlsx stored as csv if openpyxl unavailable)

class SavedQueryCreate(BaseModel):
    name: str
    sql: str
    source_id: int
    lab_mode: str = "analyst"
    test_params: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    is_shared: bool = False

class SavedQueryUpdate(SavedQueryCreate):
    pass

class AiFeedbackRequest(BaseModel):
    source_id: Optional[int] = None
    prompt: Optional[str] = None
    generated_sql: Optional[str] = None
    rating: int = Field(..., ge=1, le=2, description="1=踩 2=赞")
    execution_success: bool = False

class AnalysisSessionSave(BaseModel):
    title: str
    sql: Optional[str] = None
    columns: Optional[List[Any]] = None
    messages: List[Any]

class PublishCheckRequest(BaseModel):
    source_id: int
    sql: str
    params: Optional[Dict[str, Any]] = None
    resource_mode: str = "api"

class PublishRequest(BaseModel):
    resource_key: str
    resource_name: str
    resource_group: str = "Default"
    data_source: str
    resource_mode: str = "SQL"
    custom_sql: str
    fields_config: List[Any]
    allowed_filters: List[Any]
    default_sort: str
    status: int = 1
    cache_ttl: int = 0
    remarks: Optional[str] = None

    @validator('resource_group')
    def validate_group_not_system(cls, v):
        return validate_user_resource_group(v)

class AIRequest(BaseModel):

    sql: str

    source_type: str = Field("mysql", description="mysql or clickhouse")



class AIGenerateRequest(BaseModel):
    prompt: str
    source_id: int
    tables: Optional[List[str]] = None
    mode: Optional[str] = "api" # 'api' or 'analyst'

class AIProfileGenerateRequest(BaseModel):
    source_id: int
    table_name: str
    mode: Optional[str] = "analyst"  # 'api' or 'analyst'

class AIEditRequest(BaseModel):
    sql: str
    instruction: str
    source_id: int
    tables: Optional[List[str]] = None
    mode: Optional[str] = "api"



