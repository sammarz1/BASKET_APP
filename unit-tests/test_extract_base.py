"""Unit tests for BaseExtractor and ExtractRequest."""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

from basket_app.core.http import FetchResult
from basket_app.extract.base import BaseExtractor, ExtractRequest


class DummyExtractor(BaseExtractor):
    league = "nba"
    endpoint = "test_endpoint"

    def __init__(self, *args, requests_to_yield=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.requests_to_yield = requests_to_yield or []

    def iter_requests(self):
        yield from self.requests_to_yield


def make_fetch_result(content=b'{"ok": true}', url="https://example.com/test"):
    return FetchResult(
        url=url,
        status_code=200,
        content=content,
        content_type="application/json; charset=utf-8",
        retrieved_at=datetime.now(timezone.utc),
        elapsed_seconds=0.1,
    )


def test_extract_request_stored_key():
    req1 = ExtractRequest(url="http://x", key="nba/test.json")
    assert req1.stored_key == "nba/test.json.gz"

    req2 = ExtractRequest(url="http://x", key="nba/test.json.gz")
    assert req2.stored_key == "nba/test.json.gz"


def test_build_key():
    storage = MagicMock()
    extractor = DummyExtractor("2024-25", storage=storage)

    key = extractor.build_key(name="schedule")
    assert key == "nba/test_endpoint/season=2024-25/schedule.json"

    partitioned_key = extractor.build_key(
        "date=2024-11-01", "game_id=001", name="boxscore"
    )
    assert (
        partitioned_key
        == "nba/test_endpoint/season=2024-25/date=2024-11-01/game_id=001/boxscore.json"
    )


def test_iter_dates():
    storage = MagicMock()
    extractor = DummyExtractor(
        "2024-25",
        storage=storage,
        start=date(2024, 11, 1),
        end=date(2024, 11, 3),
    )
    dates = list(extractor.iter_dates())
    assert dates == [date(2024, 11, 1), date(2024, 11, 2), date(2024, 11, 3)]


def test_iter_dates_requires_start_and_end():
    storage = MagicMock()
    extractor = DummyExtractor("2024-25", storage=storage)
    with pytest.raises(ValueError, match="requires both 'start' and 'end'"):
        list(extractor.iter_dates())


def test_run_fetches_and_stores():
    storage = MagicMock()
    storage.object_exists.return_value = False
    storage.put_raw_bytes.return_value = "s3://bronze/nba/data.json.gz"

    client = MagicMock()
    client.get.return_value = make_fetch_result()

    req = ExtractRequest(url="https://example.com/api", key="nba/data.json")
    extractor = DummyExtractor(
        "2024-25", storage=storage, client=client, requests_to_yield=[req]
    )

    summary = extractor.run()
    assert summary.fetched == 1
    assert summary.skipped == 0
    assert summary.failed == 0
    assert summary.uris == ["s3://bronze/nba/data.json.gz"]

    client.get.assert_called_once_with(req.url, params={}, headers={})
    storage.put_raw_bytes.assert_called_once()
    call_kwargs = storage.put_raw_bytes.call_args.kwargs
    assert call_kwargs["key"] == "nba/data.json"
    assert call_kwargs["content_type"] == "application/json"
    assert call_kwargs["compress"] is True
    assert call_kwargs["metadata"]["league"] == "nba"


def test_run_skips_when_exists_and_not_overwrite():
    storage = MagicMock()
    storage.object_exists.return_value = True

    client = MagicMock()
    req = ExtractRequest(url="https://example.com/api", key="nba/data.json")
    extractor = DummyExtractor(
        "2024-25",
        storage=storage,
        client=client,
        overwrite=False,
        requests_to_yield=[req],
    )

    summary = extractor.run()
    assert summary.fetched == 0
    assert summary.skipped == 1
    assert summary.failed == 0
    client.get.assert_not_called()
    storage.put_raw_bytes.assert_not_called()


def test_run_overwrites_when_flag_set():
    storage = MagicMock()
    storage.object_exists.return_value = True
    storage.put_raw_bytes.return_value = "s3://bronze/nba/data.json.gz"

    client = MagicMock()
    client.get.return_value = make_fetch_result()

    req = ExtractRequest(url="https://example.com/api", key="nba/data.json")
    extractor = DummyExtractor(
        "2024-25",
        storage=storage,
        client=client,
        overwrite=True,
        requests_to_yield=[req],
    )

    summary = extractor.run()
    assert summary.fetched == 1
    assert summary.skipped == 0
    client.get.assert_called_once()
    storage.put_raw_bytes.assert_called_once()


def test_run_continues_on_error():
    storage = MagicMock()
    storage.object_exists.return_value = False
    storage.put_raw_bytes.return_value = "s3://bronze/ok.json.gz"

    client = MagicMock()
    # First request fails, second succeeds
    client.get.side_effect = [RuntimeError("API timeout"), make_fetch_result()]

    req1 = ExtractRequest(url="https://example.com/bad", key="bad.json")
    req2 = ExtractRequest(url="https://example.com/good", key="good.json")
    extractor = DummyExtractor(
        "2024-25", storage=storage, client=client, requests_to_yield=[req1, req2]
    )

    summary = extractor.run()
    assert summary.fetched == 1
    assert summary.failed == 1
    assert len(summary.errors) == 1
    assert summary.errors[0][0] == "bad.json"
    assert "API timeout" in summary.errors[0][1]
