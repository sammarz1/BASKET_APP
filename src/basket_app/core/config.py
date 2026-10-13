"""Application settings, loaded from the environment, config.json, and the repo-root .env file."""

from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Optional

from pydantic import Field, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

# Anchor paths to the repo root so settings resolve regardless of cwd.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"
CONFIG_JSON = PROJECT_ROOT / "config.json"


class JsonFileSource(PydanticBaseSettingsSource):
    """Settings source that loads configuration from config.json if present."""

    def __init__(self, settings_cls: type[BaseSettings], json_file: Path):
        super().__init__(settings_cls)
        self.json_file = json_file

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        if not self.json_file.exists() or self.json_file.stat().st_size == 0:
            return {}
        try:
            with open(self.json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}


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

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            JsonFileSource(settings_cls, json_file=CONFIG_JSON),
            dotenv_settings,
        )

    def save_to_json(self, path: Optional[Path] = None) -> Path:
        """Serialize current settings to config.json with indentation."""
        target = path or CONFIG_JSON
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, indent=2)
        get_settings.cache_clear()
        return target


@lru_cache
def get_settings() -> Settings:
    return Settings()
