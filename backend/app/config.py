"""
Application configuration
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "KVrocks Manager"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./kvrocks_manager.db"
    # For MySQL: mysql+aiomysql://user:password@localhost:3306/kvrocks_manager

    # JWT Authentication
    SECRET_KEY: str = os.getenv("SECRET_KEY", "fallback-only-for-dev")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Redis (for caching)
    REDIS_URL: str = "redis://localhost:6379/0"

    # KVrocks Controller (optional, set via env or UI)
    KVROCKS_CONTROLLER_URL: Optional[str] = None
    KVROCKS_CONTROLLER_TIMEOUT: int = 60
    KVROCKS_CONTROLLER_USERNAME: Optional[str] = None
    KVROCKS_CONTROLLER_PASSWORD: Optional[str] = None
    KVROCKS_DEFAULT_NAMESPACE: str = "default"

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
