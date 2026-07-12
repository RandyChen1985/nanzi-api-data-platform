from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime

class DataSourceBase(BaseModel):
    source_name: str = Field(..., description="Data source unique name")
    source_type: str = Field(..., description="Type: clickhouse, mysql, oracle, sqlserver")
    host: str = Field(..., description="Database host")
    port: int = Field(..., description="Database port")
    database_name: Optional[str] = Field(
        None,
        description="库名/Schema；Oracle 默认作 SID（与 AI Agent 一致）。按服务名连接请在 extra_params 中设置 service_name，或对 database_name 作 SERVICE_NAME 时设置 oracle_use_service_name",
    )
    username: Optional[str] = Field(None, description="Connection username")
    password: Optional[str] = Field(None, description="Connection password")
    extra_params: Optional[Dict[str, Any]] = Field(None, description="Additional params")
    description: Optional[str] = Field(None, description="Description")
    sort_order: int = Field(0, description="Sorting weight (ascending)")
    status: int = Field(1, description="1-Active, 0-Inactive")

class DataSourceCreate(DataSourceBase):
    pass

class DataSourceConnectionTest(DataSourceBase):
    source_id: Optional[int] = Field(None, description="Existing data source ID for password fallback")

class DataSourceUpdate(BaseModel):
    source_name: Optional[str] = None
    source_type: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    database_name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    extra_params: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    status: Optional[int] = None

class DataSourceResponse(DataSourceBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    @field_validator("password")
    @classmethod
    def mask_password(cls, v):
        if v:
            return "******"
        return v

    class Config:
        from_attributes = True

class DataSourceInternal(DataSourceBase):
    """Internal model that includes actual password for connection purposes"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DbProfileTaskResponse(BaseModel):
    id: int
    connection_id: int
    status: int
    total_tables: int
    processed_tables: int
    completed_profiles: int = 0
    last_profiled_at: Optional[datetime] = None
    current_table: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DbTableProfileSummaryResponse(BaseModel):
    id: int
    connection_id: int
    table_name: str
    table_type: str
    ai_term: Optional[str] = None
    ai_description: Optional[str] = None
    ai_tags: Optional[List[str]] = None
    status: int
    error_message: Optional[str] = None
    confidence_score: int = 100
    is_temporary: int = 0
    is_ignored: int = 0
    confidence_reason: Optional[str] = None
    columns_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DbTableProfileResponse(BaseModel):
    id: int
    connection_id: int
    table_name: str
    table_type: str
    engine: Optional[str] = None
    ddl: Optional[str] = None
    sample_data: Optional[Any] = None
    ai_term: Optional[str] = None
    ai_description: Optional[str] = None
    ai_tags: Optional[List[str]] = None
    columns_profile: Optional[List[Dict[str, Any]]] = None
    status: int
    error_message: Optional[str] = None
    confidence_score: int
    is_temporary: int
    is_ignored: int
    confidence_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TableProfileIgnorePayload(BaseModel):
    table_name: str
    is_ignored: int


class DataSourceTableScope(BaseModel):
    all_tables: bool = False
    tables: List[str] = []
    configured: bool = False


class DataSourceRolePermissionHolder(BaseModel):
    id: int
    role_code: str
    role_name: str
    member_count: int = 0
    table_scope: DataSourceTableScope


class DataSourceUserPermissionHolder(BaseModel):
    id: int
    user_name: str
    status: int = 1
    table_scope: DataSourceTableScope


class DataSourcePermissionsResponse(BaseModel):
    source_id: int
    source_name: str
    roles: List[DataSourceRolePermissionHolder] = []
    users: List[DataSourceUserPermissionHolder] = []
    admin_count: int = 0

