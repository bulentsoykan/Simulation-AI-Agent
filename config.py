# ABOUTME: Application configuration using Pydantic Settings
# ABOUTME: Loads settings from environment variables with defaults

from pydantic_settings import BaseSettings
from typing import Optional
import secrets


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    mcp_port: int = 8001
    debug: bool = False

    # Database
    database_url: str = "sqlite:///./simulation.db"

    # JWT Authentication
    jwt_secret_key: str = secrets.token_urlsafe(32)
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Multi-tenancy
    default_tenant_name: str = "default"

    # Simulation
    max_simulation_time: int = 86400  # 24 hours max sim time
    simulation_timeout: int = 300  # 5 minute timeout

    # ML
    ml_models_dir: str = "./ml_models"

    # Monitoring
    enable_metrics: bool = True
    metrics_port: int = 9090

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
