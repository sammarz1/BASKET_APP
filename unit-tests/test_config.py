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


def test_save_and_load_config_json(tmp_path):
    import json
    from basket_app.core.config import JsonFileSource

    cfg_file = tmp_path / "custom_config.json"
    settings = Settings(s3_bucket_name="my_test_bucket")
    settings.save_to_json(path=cfg_file)

    assert cfg_file.exists()
    with open(cfg_file, "r") as f:
        data = json.load(f)
    assert data["s3_bucket_name"] == "my_test_bucket"

    # Verify JsonFileSource loads it
    source = JsonFileSource(Settings, json_file=cfg_file)
    loaded_dict = source()
    assert loaded_dict["s3_bucket_name"] == "my_test_bucket"


def test_json_file_source_empty_or_missing(tmp_path):
    from basket_app.core.config import JsonFileSource

    missing_file = tmp_path / "nonexistent.json"
    source = JsonFileSource(Settings, json_file=missing_file)
    assert source() == {}

    empty_file = tmp_path / "empty.json"
    empty_file.touch()
    source_empty = JsonFileSource(Settings, json_file=empty_file)
    assert source_empty() == {}
