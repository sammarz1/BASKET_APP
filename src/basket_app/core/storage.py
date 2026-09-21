"""Storage service abstraction for the Bronze layer (S3 and MinIO compatible)."""

import gzip
import json
from datetime import datetime, timezone
from typing import Any, Optional

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from basket_app.core.config import get_settings


class BronzeStorage:
    """Client for storing and retrieving raw data in Bronze layer (S3 / MinIO)."""

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        bucket_name: str = "bronze",
        region_name: str = "us-east-1",
        use_ssl: bool = False,
    ):
        self.bucket_name = bucket_name
        self.region_name = region_name
        endpoint = endpoint_url if endpoint_url and endpoint_url.strip() else None

        self.s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region_name,
            use_ssl=use_ssl,
            config=Config(signature_version="s3v4"),
        )

    def ensure_bucket_exists(self) -> None:
        """Verify the bucket exists, creating it if necessary."""
        try:
            self.s3.head_bucket(Bucket=self.bucket_name)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code not in ("404", "NoSuchBucket"):
                raise
            create_kwargs: dict[str, Any] = {"Bucket": self.bucket_name}
            # AWS rejects a LocationConstraint of us-east-1 but requires it elsewhere.
            if self.region_name != "us-east-1":
                create_kwargs["CreateBucketConfiguration"] = {
                    "LocationConstraint": self.region_name
                }
            self.s3.create_bucket(**create_kwargs)

    # ------------------------------------------------------------------ writes

    def put_raw_bytes(
        self,
        key: str,
        body: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[dict[str, str]] = None,
        compress: bool = True,
    ) -> str:
        """
        Store a raw payload exactly as received (optionally gzipped).

        This is the bronze primitive: extractors should pass ``response.content``
        so the stored object is byte-identical to what the source returned.

        :param key: S3 object key (e.g. 'nba/schedule/season=2024-25/schedule.json')
        :param body: Raw payload bytes
        :param content_type: MIME type of the *uncompressed* payload
        :param metadata: Optional provenance metadata (S3 user metadata: ASCII, 2 KB max)
        :param compress: Whether to gzip the payload; appends '.gz' to the key
        :return: S3 URI of the written object (s3://bucket/key)
        """
        s3_meta = {"ingested_at": datetime.now(timezone.utc).isoformat()}
        if metadata:
            s3_meta.update({str(k): str(v) for k, v in metadata.items()})

        target_key = key
        put_kwargs: dict[str, Any] = {
            "Bucket": self.bucket_name,
            "ContentType": content_type,
            "Metadata": s3_meta,
        }
        if compress:
            if not target_key.endswith(".gz"):
                target_key = f"{target_key}.gz"
            put_kwargs["Body"] = gzip.compress(body)
            put_kwargs["ContentEncoding"] = "gzip"
        else:
            put_kwargs["Body"] = body
        put_kwargs["Key"] = target_key

        self.s3.put_object(**put_kwargs)
        return f"s3://{self.bucket_name}/{target_key}"

    def put_raw_json(
        self,
        key: str,
        data: Any,
        metadata: Optional[dict[str, str]] = None,
        compress: bool = True,
    ) -> str:
        """
        Serialize a Python object to JSON and store it. Convenience wrapper over
        :meth:`put_raw_bytes`; prefer the bytes variant for source responses.
        """
        raw_json = json.dumps(data, default=str, ensure_ascii=False).encode("utf-8")
        return self.put_raw_bytes(
            key,
            raw_json,
            content_type="application/json",
            metadata=metadata,
            compress=compress,
        )

    # ------------------------------------------------------------------- reads

    def get_raw_bytes(self, key: str) -> bytes:
        """Retrieve an object's payload, transparently decompressing gzip."""
        response = self.s3.get_object(Bucket=self.bucket_name, Key=key)
        content = response["Body"].read()
        if key.endswith(".gz") or response.get("ContentEncoding") == "gzip":
            content = gzip.decompress(content)
        return content

    def get_raw_json(self, key: str) -> dict | list:
        """Retrieve and deserialize a JSON object, decompressing if gzipped."""
        return json.loads(self.get_raw_bytes(key).decode("utf-8"))

    def object_exists(self, key: str) -> bool:
        """Check whether an object key exists in the bucket."""
        try:
            self.s3.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchKey"):
                return False
            raise

    def list_keys(self, prefix: str = "") -> list[str]:
        """List all object keys under a given prefix."""
        paginator = self.s3.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
            keys.extend(item["Key"] for item in page.get("Contents", []))
        return keys

    def delete_object(self, key: str) -> None:
        """Delete an object from the bucket."""
        self.s3.delete_object(Bucket=self.bucket_name, Key=key)


def get_bronze_storage() -> BronzeStorage:
    """Factory helper to obtain a configured BronzeStorage instance."""
    settings = get_settings()
    return BronzeStorage(
        endpoint_url=settings.s3_endpoint_url,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key,
        bucket_name=settings.s3_bucket_name,
        region_name=settings.s3_region,
        use_ssl=settings.s3_use_ssl,
    )
