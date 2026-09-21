"""Unit tests for the shared HTTP client."""

from unittest.mock import patch

from basket_app.core.http import HttpClient


class FakeResponse:
    url = "https://example.com/data?x=1"
    status_code = 200
    content = b'{"ok": true}'
    headers = {"Content-Type": "application/json; charset=utf-8"}

    def raise_for_status(self):
        pass


def test_session_has_retries_and_default_headers():
    client = HttpClient(default_headers={"X-Extra": "1"})
    assert client.session.headers["X-Extra"] == "1"
    assert client.session.headers["User-Agent"].startswith("python-requests/")
    retry = client.session.get_adapter("https://example.com").max_retries
    assert retry.total == 5 and 429 in retry.status_forcelist


def test_get_returns_fetch_result_with_provenance():
    client = HttpClient()
    client.min_interval = 0
    with patch.object(client.session, "get", return_value=FakeResponse()) as get:
        result = client.get("https://example.com/data", params={"x": 1})

    assert get.call_args.kwargs["timeout"] == 30
    assert result.content == b'{"ok": true}'
    prov = result.provenance()
    assert prov["source_url"] == "https://example.com/data?x=1"
    assert prov["http_status"] == "200"
    assert "retrieved_at" in prov


def test_throttle_sleeps_only_between_calls():
    client = HttpClient()
    client.min_interval = 10
    with patch("basket_app.core.http.time.sleep") as sleep:
        client._throttle()  # first call never sleeps
        sleep.assert_not_called()
        client._throttle()
        assert sleep.call_count == 1 and 0 < sleep.call_args[0][0] <= 10
