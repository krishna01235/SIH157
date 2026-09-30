from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    database_url: str = "sqlite:///./data/sat-sa.db"
    log_level: str = "INFO"
    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]
    allowed_origins: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]
    max_upload_bytes: int = Field(default=10_485_760, gt=0)
    max_request_bytes: int = Field(default=11_534_336, gt=0)
    max_records_per_submission: int = Field(default=10_000, gt=0)
    demo_enabled: bool = True
    frontend_dist: Path = Path(__file__).resolve().parents[2] / "frontend" / "dist"

    @field_validator("allowed_hosts", "allowed_origins", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        return [item.strip() for item in value.split(",") if item.strip()] if isinstance(value, str) else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
