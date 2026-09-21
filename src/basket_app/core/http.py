"""Shared HTTP client: retries with backoff, timeouts, rate limiting, provenance."""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from basket_app.core.config import get_settings

log = logging.getLogger(__name__)

TIMEOUT_SECONDS = 30
MAX_RETRIES = 5
BACKOFF_FACTOR = 1.0


@dataclass
class FetchResult:
    """Raw HTTP response plus the provenance needed to describe a bronze object."""

    url: str
    status_code: int
    content: bytes
    content_type: str
    retrieved_at: datetime
    elapsed_seconds: float

    def provenance(self) -> dict[str, str]:
        """Terse, ASCII-safe metadata suitable for S3 user metadata."""
        return {
            "source_url": self.url,
            "http_status": str(self.status_code),
            "retrieved_at": self.retrieved_at.isoformat(),
        }


class HttpClient:
    """
    requests.Session with retry/backoff on 429/5xx, a default timeout and a
    minimum interval between calls. Returns :class:`FetchResult` objects ready
    to be written to bronze.

    The User-Agent is deliberately left as the requests default: some WAFs
    (e.g. ESPN) reject spoofed browser UAs. Sources that need browser headers
    pass them via ``default_headers``.
    """

    def __init__(self, default_headers: Optional[dict[str, str]] = None):
        retry = Retry(
            total=MAX_RETRIES,
            backoff_factor=BACKOFF_FACTOR,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        self.session = requests.Session()
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.mount("http://", HTTPAdapter(max_retries=retry))
        self.session.headers["Accept"] = "application/json, text/plain, */*"
        if default_headers:
            self.session.headers.update(default_headers)
        self.min_interval = get_settings().http_min_interval_seconds
        self._last_call: Optional[float] = None

    def get(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> FetchResult:
        """GET a URL, raising on non-2xx after retries are exhausted."""
        self._throttle()
        started = time.monotonic()
        retrieved_at = datetime.now(timezone.utc)
        response = self.session.get(
            url, params=params, headers=headers, timeout=TIMEOUT_SECONDS
        )
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
        )

    def _throttle(self) -> None:
        if self._last_call is not None:
            remaining = self.min_interval - (time.monotonic() - self._last_call)
            if remaining > 0:
                time.sleep(remaining)
        self._last_call = time.monotonic()
