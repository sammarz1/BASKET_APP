"""Unit tests for the shared HTTP client."""

from unittest.mock import patch

import requests

from basket_app.core.config import HttpSettings
from basket_app.core.http import HttpClient, RateLimiter, build_session


def test_rate_limiter_sleeps_only_when_needed():
    limiter = RateLimiter(min_interval_seconds=10)
    with patch("basket_app.core.http.time.sleep") as sleep:
        limiter.wait()  # first call never sleeps
        sleep.assert_not_called()
        limiter.wait()  # second call is well within the interval
        assert sleep.call_count == 1
        assert 0 < sleep.call_args[0][0] <= 10


def test_build_session_sets_headers_and_retries():
    settings = HttpSettings(http_max_retries=3, http_user_agent="basket-test")
    session = build_session(settings, default_headers={"X-Extra": "1"})
    assert session.headers["User-Agent"] == "basket-test"
    assert session.headers["X-Extra"] == "1"
    adapter = session.get_adapter("https://example.com")
    assert adapter.max_retries.total == 3
    assert 429 in adapter.max_retries.status_forcelist


def test_build_session_keeps_requests_default_user_agent_when_unset():
    session = build_session(HttpSettings(http_user_agent=None))
    assert session.headers["User-Agent"].startswith("python-requests/")


def test_http_client_returns_fetch_result_with_provenance():
    class FakeResponse:
        url = "https://example.com/data?x=1"
        status_code = 200
        content = b'{"ok": true}'
        headers = {"Content-Type": "application/json; charset=utf-8"}

        def raise_for_status(self):
            pass

    session = requests.Session()
    with patch.object(session, "get", return_value=FakeResponse()) as get:
        client = HttpClient(
            settings=HttpSettings(http_min_interval_seconds=0), session=session
        )
        result = client.get("https://example.com/data", params={"x": 1})

    get.assert_called_once()
    assert result.content == b'{"ok": true}'
    assert result.status_code == 200
    prov = result.provenance()
    assert prov["source_url"] == "https://example.com/data?x=1"
    assert prov["http_status"] == "200"
    assert "retrieved_at" in prov
