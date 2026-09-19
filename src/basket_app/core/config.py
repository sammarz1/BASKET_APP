"""Configuration management for storage, HTTP and application settings."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor the .env file to the repo root so settings resolve regardless of cwd.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"


class StorageSettings(BaseSettings):
    """
    Object storage configuration.

    Supports MinIO for local development and AWS S3 in production.
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


class HttpSettings(BaseSettings):
    """HTTP client configuration shared by all extractors."""

    http_timeout_seconds: float = Field(
        default=30.0,
        description="Per-request timeout (connect + read).",
    )
    http_max_retries: int = Field(
        default=5,
        description="Retries on connection errors, 429 and 5xx responses.",
    )
    http_backoff_factor: float = Field(
        default=1.0,
        description="Exponential backoff base in seconds between retries.",
    )
    http_min_interval_seconds: float = Field(
        default=1.0,
        description="Minimum delay between consecutive requests (rate limiting).",
    )
    http_user_agent: Optional[str] = Field(
        default=None,
        description=(
            "User-Agent header override. Leave unset to use the requests default: "
            "some WAFs (e.g. ESPN) reject spoofed browser UAs without matching TLS "
            "fingerprints. Sources that need browser headers set them per extractor."
        ),
    )

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> StorageSettings:
    return StorageSettings()


@lru_cache
def get_http_settings() -> HttpSettings:
    return HttpSettings()
