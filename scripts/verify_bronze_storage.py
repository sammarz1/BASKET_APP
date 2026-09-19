"""Verification script to test MinIO storage connection, upload, and retrieval."""

import sys
from datetime import datetime, timezone
from basket_app.core.storage import get_bronze_storage
from basket_app.core.config import get_settings


def run_verification() -> None:
    settings = get_settings()
    print("=" * 60)
    print("Basket App - Bronze Storage Verification (Local MinIO)")
    print("=" * 60)
    print(f"Endpoint URL : {settings.s3_endpoint_url}")
    print(f"Bucket Name  : {settings.s3_bucket_name}")
    print(f"SSL Enabled  : {settings.s3_use_ssl}")
    print("-" * 60)

    storage = get_bronze_storage()

    print("[1/4] Checking/creating bucket...")
    try:
        storage.ensure_bucket_exists()
        print(f"      Bucket '{settings.s3_bucket_name}' is ready.")
    except Exception as exc:
        print(f"      ERROR connecting to MinIO: {exc}")
        print("\nPlease ensure MinIO is running (`docker compose up -d`).")
        sys.exit(1)

    test_key = (
        f"_healthcheck/test_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    )
    sample_payload = {
        "status": "success",
        "description": "Bronze layer MinIO integration test",
        "metadata": {
            "source": "local_dev",
            "project": "BASKET_APP",
            "leagues_planned": ["NBA", "Euroleague"],
        },
        "sample_data": {
            "game_id": "test-001",
            "home_team": "Real Madrid",
            "away_team": "Boston Celtics",
            "score": [108, 105],
        },
    }

    print(f"[2/4] Uploading compressed raw JSON to '{test_key}.gz'...")
    s3_uri = storage.put_raw_json(
        key=test_key,
        data=sample_payload,
        metadata={"source_test": "verify_script"},
        compress=True,
    )
    print(f"      Uploaded successfully -> {s3_uri}")

    print("[3/4] Reading back payload and verifying contents...")
    actual_key = f"{test_key}.gz"
    retrieved = storage.get_raw_json(actual_key)
    assert (
        retrieved == sample_payload
    ), "Retrieved data does not match original payload!"
    print("      Data integrity verified: retrieved payload matches byte-for-byte.")

    print("[4/4] Listing objects under '_healthcheck/' prefix...")
    keys = storage.list_keys(prefix="_healthcheck/")
    print(f"      Found {len(keys)} object(s) in prefix: {keys[-3:]}")

    print("-" * 60)
    print("SUCCESS: MinIO bronze layer is fully functional!")
    print(f"Access the MinIO Web Console at: http://localhost:9001")
    print(f"Username: {settings.s3_access_key_id}")
    print(f"Password: {settings.s3_secret_access_key}")
    print(f"Bucket  : {settings.s3_bucket_name}")
    print("=" * 60)


if __name__ == "__main__":
    run_verification()
