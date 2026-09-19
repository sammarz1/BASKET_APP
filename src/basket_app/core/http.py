"""Shared HTTP client: retries with backoff, timeouts, rate limiting, provenance."""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from basket_app.core.config import HttpSettings, get_http_settings

log = logging.getLogger(__name__)


@dataclass
class FetchResult:
    """Raw HTTP response plus the provenance needed to describe a bronze object."""

    url: str
    status_code: int
    content: bytes
    content_type: str
    retrieved_at: datetime
    elapsed_seconds: float
    params: dict[str, Any] = field(default_factory=dict)

    def provenance(self) -> dict[str, str]:
        """Terse, ASCII-safe metadata suitable for S3 user metadata."""
        return {
            "source_url": self.url,
            "http_status": str(self.status_code),
            "retrieved_at": self.retrieved_at.isoformat(),
        }


class RateLimiter:
    """Enforces a minimum wall-clock interval between consecutive calls."""

    def __init__(self, min_interval_seconds: float):
        self.min_interval = min_interval_seconds
        self._last_call: Optional[float] = None

    def wait(self) -> None:
        if self._last_call is not None:
            remaining = self.min_interval - (time.monotonic() - self._last_call)
            if remaining > 0:
                time.sleep(remaining)
        self._last_call = time.monotonic()


class _TimeoutAdapter(HTTPAdapter):
    """HTTPAdapter that applies a default timeout to every request."""

    def __init__(self, timeout: float, **kwargs: Any):
        self.timeout = timeout
        super().__init__(**kwargs)

    def send(self, request, **kwargs):  # type: ignore[override]
        kwargs.setdefault("timeout", self.timeout)
        return super().send(request, **kwargs)


def build_session(
    settings: Optional[HttpSettings] = None,
    default_headers: Optional[dict[str, str]] = None,
) -> requests.Session:
    """Create a requests.Session with retry/backoff, timeout and default headers."""
    settings = settings or get_http_settings()
    retry = Retry(
        total=settings.http_max_retries,
        connect=settings.http_max_retries,
        read=settings.http_max_retries,
        status=settings.http_max_retries,
        backoff_factor=settings.http_backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = _TimeoutAdapter(timeout=settings.http_timeout_seconds, max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers["Accept"] = "application/json, text/plain, */*"
    if settings.http_user_agent:
        session.headers["User-Agent"] = settings.http_user_agent
    if default_headers:
        session.headers.update(default_headers)
    return session


class HttpClient:
    """
    Thin wrapper over a configured Session that rate-limits and returns
    :class:`FetchResult` objects ready to be written to bronze.
    """

    def __init__(
        self,
        settings: Optional[HttpSettings] = None,
        default_headers: Optional[dict[str, str]] = None,
        session: Optional[requests.Session] = None,
    ):
        self.settings = settings or get_http_settings()
        self.session = session or build_session(self.settings, default_headers)
        self.rate_limiter = RateLimiter(self.settings.http_min_interval_seconds)

    def get(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> FetchResult:
        """GET a URL, raising on non-2xx after retries are exhausted."""
        self.rate_limiter.wait()
        started = time.monotonic()
        retrieved_at = datetime.now(timezone.utc)
        response = self.session.get(url, params=params, headers=headers)
        elapsed = time.monotonic() - started
        log.debug("GET %s -> %s in %.2fs", response.url, response.status_code, elapsed)
        response.raise_for_status()
        return FetchResult(
            url=response.url,
            status_code=response.status_code,
            content=response.content,
            content_type=response.headers.get(
                "Content-Type", "application/octet-stream"
            ),
            retrieved_at=retrieved_at,
            elapsed_seconds=elapsed,
            params=dict(params or {}),
        )
