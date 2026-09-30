from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    database_url: str = "sqlite:///./data/sat-sa.db"
    log_level: str = "INFO"
    allowed_hosts: str = "localhost,127.0.0.1"
    allowed_origins: str = "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173,http://127.0.0.1:5173"
    max_upload_bytes: int = Field(default=10_485_760, gt=0)
    max_request_bytes: int = Field(default=11_534_336, gt=0)
    max_records_per_submission: int = Field(default=10_000, gt=0)
    demo_enabled: bool = True
    frontend_dist: Path = Path(__file__).resolve().parents[2] / "frontend" / "dist"

    @model_validator(mode="after")
    def validate_limits(self) -> "Settings":
        if self.max_request_bytes <= self.max_upload_bytes:
            raise ValueError("MAX_REQUEST_BYTES must exceed MAX_UPLOAD_BYTES")
        if not self.allowed_host_list or not self.allowed_origin_list:
            raise ValueError("ALLOWED_HOSTS and ALLOWED_ORIGINS cannot be empty")
        return self

    @property
    def allowed_host_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_hosts.split(",") if item.strip()]

    @property
    def allowed_origin_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
