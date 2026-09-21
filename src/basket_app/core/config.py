"""Application settings, loaded from the environment and the repo-root .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor the .env file to the repo root so settings resolve regardless of cwd.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """
    Object storage (MinIO locally, AWS S3 in production) and HTTP settings.
    """

    s3_endpoint_url: Optional[str] = Field(
        default="http://localhost:9000",
        description="S3 endpoint URL. Set to None or empty in AWS S3 production.",
    )
    s3_access_key_id: Optional[str] = Field(
        default="minioadmin",
        description="Access key or AWS_ACCESS_KEY_ID.",
    )
    s3_secret_access_key: Optional[str] = Field(
        default="minioadmin",
        description="Secret key or AWS_SECRET_ACCESS_KEY.",
    )
    s3_bucket_name: str = Field(
        default="bronze",
        description="Target bucket name for raw bronze ingestion.",
    )
    s3_region: str = Field(
        default="us-east-1",
        description="S3 region name.",
    )
    s3_use_ssl: bool = Field(
        default=False,
        description="Whether to use SSL (True for HTTPS in AWS, False for local MinIO).",
    )
    http_min_interval_seconds: float = Field(
        default=1.0,
        description="Minimum delay between consecutive HTTP requests (rate limiting).",
    )

    @field_validator("s3_endpoint_url", mode="before")
    @classmethod
    def clean_endpoint_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v_str = str(v).strip()
        return v_str if v_str else None

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
