"""Base classes for bronze extractors.

An extractor describes *what* to fetch (a sequence of :class:`ExtractRequest`)
and *where* it lands in the bucket. :class:`BaseExtractor.run` handles the rest:
rate-limited fetching, skip-if-exists idempotency, provenance metadata and
writing the raw bytes to bronze.

Bronze key convention (Hive-style partitions so the silver layer can prune):

    {league}/{endpoint}/season={season}/[extra=partitions/]{name}.json.gz
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
    """One HTTP request and the bronze key its response should be stored under."""

    url: str
    key: str
    params: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def stored_key(self) -> str:
        """Key as it will appear in the bucket (extractors always gzip)."""
        return self.key if self.key.endswith(".gz") else f"{self.key}.gz"


@dataclass
class ExtractSummary:
    fetched: int = 0
    skipped: int = 0
    failed: int = 0
    uris: list[str] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.fetched + self.skipped + self.failed


class BaseExtractor(ABC):
    """
    Subclasses set ``league`` / ``endpoint`` and implement :meth:`iter_requests`.
    Optionally override ``default_headers`` for sources that need specific headers.

    :param season: league-specific season label used for the bronze partition
        (NBA ``2025-26``, EuroLeague ``E2025``)
    :param start: optional first date for date-partitioned endpoints
    :param end: optional last date (inclusive) for date-partitioned endpoints
    """

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
    ):
        self.season = season
        self.start = start
        self.end = end
        self.storage = storage
        self.client = client or HttpClient(default_headers=self.default_headers)
        self.overwrite = overwrite
        self.log = logging.getLogger(f"{__name__}.{self.league}.{self.endpoint}")

    @abstractmethod
    def iter_requests(self) -> Iterable[ExtractRequest]:
        """Yield the requests this extractor should perform."""

    def build_key(self, *parts: str, name: str) -> str:
        """Build a bronze key: league/endpoint/season=<season>/<parts>/<name>.json"""
        segments = [
            self.league,
            self.endpoint,
            f"season={self.season}",
            *parts,
            f"{name}.json",
        ]
        return "/".join(s.strip("/") for s in segments if s)

    def iter_dates(self) -> Iterator[date]:
        """Yield each date in [start, end]; both must be set."""
        if self.start is None or self.end is None:
            raise ValueError(
                f"{self.league}/{self.endpoint} requires --start and --end"
            )
        current = self.start
        while current <= self.end:
            yield current
            current += timedelta(days=1)

    def run(self) -> ExtractSummary:
        summary = ExtractSummary()
        for request in self.iter_requests():
            if not self.overwrite and self.storage.object_exists(request.stored_key):
                self.log.info("skip (exists): %s", request.stored_key)
                summary.skipped += 1
                continue
            try:
                uri = self.fetch_and_store(request)
            except Exception as exc:  # noqa: BLE001 - keep going, report at the end
                self.log.error("failed %s: %s", request.url, exc)
                summary.failed += 1
                summary.errors.append((request.key, str(exc)))
                continue
            summary.fetched += 1
            summary.uris.append(uri)
        self.log.info(
            "done: fetched=%d skipped=%d failed=%d",
            summary.fetched,
            summary.skipped,
            summary.failed,
        )
        return summary

    def fetch_and_store(self, request: ExtractRequest) -> str:
        result = self.client.get(
            request.url, params=request.params, headers=request.headers
        )
        metadata = {
            "league": self.league,
            "endpoint": self.endpoint,
            **result.provenance(),
            **request.metadata,
        }
        uri = self.storage.put_raw_bytes(
            request.key,
            result.content,
            content_type=_base_content_type(result.content_type),
            metadata=metadata,
            compress=True,
        )
        self.log.info(
            "stored %s (%d bytes, %.2fs)",
            uri,
            len(result.content),
            result.elapsed_seconds,
        )
        return uri


def _base_content_type(value: str) -> str:
    """'application/json; charset=utf-8' -> 'application/json'."""
    return value.split(";", 1)[0].strip() or "application/octet-stream"
