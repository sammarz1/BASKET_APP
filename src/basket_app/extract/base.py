"""Base classes for Bronze extractors.

An extractor defines what to fetch (via ExtractRequest) and where it lands in storage.
BaseExtractor handles the rest: rate-limited fetching, skip-if-exists idempotency,
provenance metadata, and compressed writing to Bronze storage.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Iterable, Iterator, Optional

from basket_app.core.http import HttpClient
from basket_app.core.storage import BronzeStorage

log = logging.getLogger(__name__)


@dataclass
class ExtractRequest:
    """A single HTTP request and the bronze key where its response should be stored."""

    url: str
    key: str
    params: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def stored_key(self) -> str:
        """Target key in storage (extractors store gzipped payloads)."""
        return self.key if self.key.endswith(".gz") else f"{self.key}.gz"


@dataclass
class ExtractSummary:
    """Summary of an extractor run."""

    fetched: int = 0
    skipped: int = 0
    failed: int = 0
    uris: list[str] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.fetched + self.skipped + self.failed


class BaseExtractor(ABC):
    """Abstract base class for all bronze layer extractors."""

    league: str
    endpoint: str
    default_headers: dict[str, str] = {}

    def __init__(
        self,
        season: str,
        *,
        storage: BronzeStorage,
        client: Optional[HttpClient] = None,
        overwrite: bool = False,
        start: Optional[date] = None,
        end: Optional[date] = None,
        limit: Optional[int] = None,
    ):
        self.season = season
        self.storage = storage
        self.client = client or HttpClient(default_headers=self.default_headers)
        self.overwrite = overwrite
        self.start = start
        self.end = end
        self.limit = limit
        self.log = logging.getLogger(f"{__name__}.{self.league}.{self.endpoint}")

    @abstractmethod
    def iter_requests(self) -> Iterable[ExtractRequest]:
        """Yield the requests to be fetched."""

    def build_key(self, *parts: str, name: str) -> str:
        """Build a Hive-style bronze storage key:
        {league}/{endpoint}/season={season}/[extra_parts/]{name}.json
        """
        segments = [
            self.league,
            self.endpoint,
            f"season={self.season}",
            *parts,
            f"{name}.json",
        ]
        return "/".join(s.strip("/") for s in segments if s)

    def iter_dates(self) -> Iterator[date]:
        """Yield each date from start to end (inclusive)."""
        if self.start is None or self.end is None:
            raise ValueError(
                f"{self.league}/{self.endpoint} requires both 'start' and 'end' dates"
            )
        current = self.start
        while current <= self.end:
            yield current
            current += timedelta(days=1)

    def run(self) -> ExtractSummary:
        """Execute the extraction: skip existing objects, fetch new ones, record summary."""
        summary = ExtractSummary()
        count = 0
        for request in self.iter_requests():
            if self.limit is not None and count >= self.limit:
                self.log.info("limit reached (%d), stopping", self.limit)
                break
            count += 1

            if not self.overwrite and self.storage.object_exists(request.stored_key):
                self.log.info("skip (exists): %s", request.stored_key)
                summary.skipped += 1
                continue

            try:
                uri = self.fetch_and_store(request)
            except Exception as exc:  # noqa: BLE001
                self.log.error("failed %s: %s", request.url, exc)
                summary.failed += 1
                summary.errors.append((request.key, str(exc)))
                continue

            summary.fetched += 1
            summary.uris.append(uri)

        self.log.info(
            "finished run: fetched=%d skipped=%d failed=%d",
            summary.fetched,
            summary.skipped,
            summary.failed,
        )
        return summary

    def fetch_and_store(self, request: ExtractRequest) -> str:
        """Fetch a single request and write its payload to bronze storage."""
        result = self.client.get(
            request.url, params=request.params, headers=request.headers
        )
        metadata = {
            "league": self.league,
            "endpoint": self.endpoint,
            **result.provenance(),
            **request.metadata,
        }
        content_type = (
            result.content_type.split(";", 1)[0].strip() or "application/octet-stream"
        )
        uri = self.storage.put_raw_bytes(
            key=request.key,
            body=result.content,
            content_type=content_type,
            metadata=metadata,
            compress=True,
        )
        self.log.info("stored %s (%d bytes)", uri, len(result.content))
        return uri
