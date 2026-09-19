"""Unit tests for BaseExtractor using in-memory storage and a fake HTTP client."""

from datetime import datetime, timezone
from typing import Iterable

import pytest

from basket_app.core.http import FetchResult
from basket_app.extract.base import BaseExtractor, ExtractRequest


class FakeStorage:
    def __init__(self):
        self.objects: dict[str, tuple[bytes, dict]] = {}

    def object_exists(self, key: str) -> bool:
        return key in self.objects

    def put_raw_bytes(self, key, body, content_type, metadata, compress):
        stored = key if key.endswith(".gz") else f"{key}.gz"
        self.objects[stored] = (body, {"content_type": content_type, **metadata})
        return f"s3://bronze/{stored}"


class FakeClient:
    def __init__(self, responses: dict[str, bytes], fail: set[str] = frozenset()):
        self.responses = responses
        self.fail = fail
        self.calls: list[str] = []

    def get(self, url, params=None, headers=None) -> FetchResult:
        self.calls.append(url)
        if url in self.fail:
            raise RuntimeError("boom")
        return FetchResult(
            url=url,
            status_code=200,
            content=self.responses[url],
            content_type="application/json; charset=utf-8",
            retrieved_at=datetime.now(timezone.utc),
            elapsed_seconds=0.01,
        )


class DummyExtractor(BaseExtractor):
    league = "test"
    endpoint = "things"

    def __init__(self, urls: list[str], **kwargs):
        super().__init__("2025", **kwargs)
        self.urls = urls

    def iter_requests(self) -> Iterable[ExtractRequest]:
        for i, url in enumerate(self.urls):
            yield ExtractRequest(
                url=url,
                key=self.build_key(name=f"item_{i}"),
                metadata={"item": str(i)},
            )


def test_build_key_layout():
    ext = DummyExtractor([], storage=FakeStorage(), client=FakeClient({}))
    assert ext.build_key("date=2025-01-01", name="g1") == (
        "test/things/season=2025/date=2025-01-01/g1.json"
    )


def test_iter_dates_inclusive_and_requires_range():
    from datetime import date

    ext = DummyExtractor([], storage=FakeStorage(), client=FakeClient({}))
    with pytest.raises(ValueError):
        list(ext.iter_dates())
    ext.start, ext.end = date(2025, 1, 30), date(2025, 2, 1)
    assert [d.isoformat() for d in ext.iter_dates()] == [
        "2025-01-30",
        "2025-01-31",
        "2025-02-01",
    ]


def test_run_stores_raw_bytes_with_provenance():
    storage = FakeStorage()
    client = FakeClient({"u1": b'{"a":1}', "u2": b"[]"})
    summary = DummyExtractor(["u1", "u2"], storage=storage, client=client).run()

    assert summary.fetched == 2 and summary.skipped == 0 and summary.failed == 0
    body, meta = storage.objects["test/things/season=2025/item_0.json.gz"]
    assert body == b'{"a":1}'  # byte-identical, never re-serialized
    assert meta["content_type"] == "application/json"
    assert meta["league"] == "test"
    assert meta["endpoint"] == "things"
    assert meta["source_url"] == "u1"
    assert meta["item"] == "0"


def test_run_skips_existing_unless_overwrite():
    storage = FakeStorage()
    storage.objects["test/things/season=2025/item_0.json.gz"] = (b"old", {})
    client = FakeClient({"u1": b"new"})

    summary = DummyExtractor(["u1"], storage=storage, client=client).run()
    assert summary.skipped == 1 and client.calls == []
    assert storage.objects["test/things/season=2025/item_0.json.gz"][0] == b"old"

    summary = DummyExtractor(
        ["u1"], storage=storage, client=client, overwrite=True
    ).run()
    assert summary.fetched == 1 and client.calls == ["u1"]
    assert storage.objects["test/things/season=2025/item_0.json.gz"][0] == b"new"


def test_run_continues_after_failure():
    storage = FakeStorage()
    client = FakeClient({"u2": b"ok"}, fail={"u1"})
    summary = DummyExtractor(["u1", "u2"], storage=storage, client=client).run()
    assert summary.failed == 1 and summary.fetched == 1
    assert summary.errors[0][1] == "boom"
    assert len(storage.objects) == 1
