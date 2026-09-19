"""Integration tests for BronzeStorage against local MinIO."""

import uuid
import pytest
from botocore.exceptions import EndpointConnectionError
from basket_app.core.storage import get_bronze_storage


@pytest.fixture(scope="module")
def storage():
    client = get_bronze_storage()
    try:
        client.ensure_bucket_exists()
    except (EndpointConnectionError, Exception) as exc:
        pytest.skip(f"MinIO is not available: {exc}")
    return client


def test_put_and_get_raw_json_compressed(storage):
    key = f"tests/integration_{uuid.uuid4().hex}.json"
    data = {"test_id": 123, "league": "NBA", "score": 99}

    s3_uri = storage.put_raw_json(key, data, compress=True)
    expected_key = f"{key}.gz"

    assert s3_uri.endswith(expected_key)
    assert storage.object_exists(expected_key) is True

    retrieved = storage.get_raw_json(expected_key)
    assert retrieved == data

    # Clean up test object
    storage.delete_object(expected_key)
    assert storage.object_exists(expected_key) is False


def test_put_and_get_raw_json_uncompressed(storage):
    key = f"tests/integration_uncompressed_{uuid.uuid4().hex}.json"
    data = {"test_id": 456, "league": "Euroleague"}

    s3_uri = storage.put_raw_json(key, data, compress=False)
    assert s3_uri.endswith(key)
    assert storage.object_exists(key) is True

    retrieved = storage.get_raw_json(key)
    assert retrieved == data

    storage.delete_object(key)
    assert storage.object_exists(key) is False
