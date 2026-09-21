"""Unit tests for configuration settings."""

from basket_app.core.config import Settings


def test_storage_settings_defaults():
    settings = Settings()
    assert settings.s3_bucket_name == "bronze"
    assert settings.s3_region == "us-east-1"


def test_clean_endpoint_url_empty_string():
    settings = Settings(s3_endpoint_url="  ")
    assert settings.s3_endpoint_url is None


def test_clean_endpoint_url_valid():
    settings = Settings(s3_endpoint_url="http://localhost:9000")
    assert settings.s3_endpoint_url == "http://localhost:9000"
