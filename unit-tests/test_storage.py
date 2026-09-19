"""Unit tests for BronzeStorage with a stubbed S3 client (no network)."""

import gzip
from unittest.mock import MagicMock

import pytest

from basket_app.core.storage import BronzeStorage, _validate_metadata


@pytest.fixture
def storage():
    s = BronzeStorage(endpoint_url="http://localhost:9000", bucket_name="bronze")
    s.s3 = MagicMock()
    return s


def test_put_raw_bytes_gzips_and_appends_suffix(storage):
    uri = storage.put_raw_bytes(
        "nba/x.json",
        b'{"a":1}',
        content_type="application/json",
        metadata={"season": "2025-26"},
    )
    assert uri == "s3://bronze/nba/x.json.gz"
    kwargs = storage.s3.put_object.call_args.kwargs
    assert kwargs["Key"] == "nba/x.json.gz"
    assert kwargs["ContentEncoding"] == "gzip"
    assert kwargs["ContentType"] == "application/json"
    assert gzip.decompress(kwargs["Body"]) == b'{"a":1}'
    assert kwargs["Metadata"]["season"] == "2025-26"
    assert "ingested_at" in kwargs["Metadata"]


def test_put_raw_bytes_uncompressed(storage):
    uri = storage.put_raw_bytes("nba/x.json", b"abc", compress=False)
    assert uri == "s3://bronze/nba/x.json"
    kwargs = storage.s3.put_object.call_args.kwargs
    assert kwargs["Body"] == b"abc"
    assert "ContentEncoding" not in kwargs


def test_put_raw_json_delegates_to_bytes(storage):
    storage.put_raw_json("k.json", {"b": 2, "a": "é"}, compress=False)
    kwargs = storage.s3.put_object.call_args.kwargs
    assert kwargs["Body"] == '{"b": 2, "a": "é"}'.encode("utf-8")
    assert kwargs["ContentType"] == "application/json"


def test_metadata_validation_rejects_non_ascii_and_oversize():
    with pytest.raises(ValueError):
        _validate_metadata({"k": "é"})
    with pytest.raises(ValueError):
        _validate_metadata({"k": "x" * 3000})
    _validate_metadata({"k": "fine"})


def test_ensure_bucket_sets_location_constraint_outside_us_east_1():
    from botocore.exceptions import ClientError

    s = BronzeStorage(endpoint_url=None, bucket_name="b", region_name="eu-west-1")
    s.s3 = MagicMock()
    s.s3.head_bucket.side_effect = ClientError({"Error": {"Code": "404"}}, "HeadBucket")
    s.ensure_bucket_exists()
    s.s3.create_bucket.assert_called_once_with(
        Bucket="b", CreateBucketConfiguration={"LocationConstraint": "eu-west-1"}
    )
