from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List, Optional

class Settings(BaseSettings):
    API_SERVICE_ENV: str = "dev"
    API_SERVICE_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    ALLOWED_ORIGINS: List[str] = ["*"]
    # Background jobs: set 0 when running dedicated scheduler process
    ENABLE_SCHEDULER: bool = True
    WEB_CONCURRENCY: int = 2
    # Audit log response body max chars stored in DB (0 = disable body capture)
    AUDIT_RESPONSE_BODY_MAX_CHARS: int = 4096

    # MySQL
    MYSQL_HOST: str
    MYSQL_PORT: int = 3306
    MYSQL_DB: str
    MYSQL_USER: str
    MYSQL_PASSWORD: str
    MYSQL_POOL_SIZE: int = 100

    # Redis
    REDIS_HOST: str
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None  # 改为 Optional 且默认为 None
    REDIS_ENABLE: bool = True

    # Security - API Key Encryption
    # Fernet Key (32 url-safe base64-encoded bytes)
    ENCRYPTION_KEY: str

    # SSO Configuration
    SSO_API_URL: str = "https://yovole.net/api/v1/user/check/login"
    SSO_ACCESS_TOKEN: str = "laplace"
    SSO_REQUEST_SYSTEM: str = "YUNSHU_API_DATA_PLATFORM"
    SSO_REQUEST_BUSINESS: str = "USER-LOGIN"
    SSO_TIMEOUT: int = 30

    class Config:
        env_file = ".env"
        extra = "ignore"  # Allow extra fields in .env

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
