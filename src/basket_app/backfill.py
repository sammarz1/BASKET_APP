"""Bulk backfill orchestrator across leagues, seasons, and data tiers."""

from dataclasses import dataclass, field
from datetime import date
import logging
from typing import Optional

from basket_app.core.storage import BronzeStorage, get_bronze_storage
from basket_app.extract.base import ExtractSummary
from basket_app.extract.registry import get_extractor_class

log = logging.getLogger(__name__)

# Topological order of ingestion per league
LEAGUE_ORDERED_ENDPOINTS: dict[str, list[str]] = {
    "euroleague": [
        "games",  # Tier 1: Calendars
        "clubs",  # Tier 2: Teams
        "standings",  # Tier 2: Standings
        "people",  # Tier 2: People directory
        "roster",  # Tier 3: Rosters (discovers clubs)
        "boxscore",  # Tier 3: Boxscores (discovers games)
        "pbp",  # Tier 3: Play-by-play (discovers games)
        "shots",  # Tier 3: Shot charts (discovers games)
    ],
    "nba": [
        "teams",  # Tier 1: Teams
        "standings",  # Tier 1: Standings
        "schedule",  # Tier 1: League Schedule
        "roster",  # Tier 2: Rosters (discovers teams)
        "scoreboard",  # Tier 2: Daily scoreboards
        "summary",  # Tier 3: Game Summaries (discovers games from scoreboards)
        "player",  # Tier 4: Player profiles (discovers athletes from rosters)
    ],
}


@dataclass
class BackfillSummary:
    """Aggregated results of a multi-season or multi-endpoint backfill."""

    seasons: list[str] = field(default_factory=list)
    endpoints: list[str] = field(default_factory=list)
    total_fetched: int = 0
    total_skipped: int = 0
    total_failed: int = 0
    endpoint_summaries: dict[str, ExtractSummary] = field(default_factory=dict)
    errors: list[tuple[str, str]] = field(default_factory=list)


def parse_season_range(league: str, start: str, end: str) -> list[str]:
    """Expand a start and end season into an inclusive list of seasons."""
    league = league.lower().strip()
    start = start.strip()
    end = end.strip()

    if league == "euroleague":
        comp = start[0].upper()
        if not end[0].upper() == comp:
            raise ValueError(
                f"Season prefixes must match (e.g. {comp}2020 to {comp}2024)"
            )
        start_year = int(start[1:])
        end_year = int(end[1:])
        if start_year > end_year:
            raise ValueError(f"Start season {start} is after end season {end}")
        return [f"{comp}{y}" for y in range(start_year, end_year + 1)]

    if league == "nba":
        start_y = int(start.split("-")[0]) if "-" in start else int(start)
        end_y = int(end.split("-")[0]) if "-" in end else int(end)
        if start_y > end_y:
            raise ValueError(f"Start season {start} is after end season {end}")
        return [f"{y}-{str(y + 1)[2:]}" for y in range(start_y, end_y + 1)]

    raise ValueError(f"Unsupported league for season ranges: {league}")


def resolve_endpoints(
    league: str,
    include: Optional[list[str]] = None,
    exclude: Optional[list[str]] = None,
) -> list[str]:
    """Filter and sort endpoints to run in safe dependency order."""
    league = league.lower().strip()
    available = LEAGUE_ORDERED_ENDPOINTS.get(league, [])
    if not available:
        raise ValueError(f"No configured pipeline for league: {league}")

    if include:
        clean_include = [e.lower().strip() for e in include]
        invalid = [e for e in clean_include if e not in available]
        if invalid:
            raise ValueError(
                f"Unknown endpoint(s) {invalid}. Available for {league}: {available}"
            )
        ordered = [e for e in available if e in clean_include]
    else:
        ordered = list(available)

    if exclude:
        clean_exclude = [e.lower().strip() for e in exclude]
        ordered = [e for e in ordered if e not in clean_exclude]

    return ordered


def default_nba_season_dates(season: str) -> tuple[date, date]:
    """Estimate the approximate date boundaries for an NBA season."""
    year = int(season.split("-")[0]) if "-" in season else int(season)
    return date(year, 10, 15), date(year + 1, 6, 25)


class BackfillOrchestrator:
    """Orchestrates multi-season and multi-endpoint data ingestion."""

    def __init__(self, storage: Optional[BronzeStorage] = None):
        self.storage = storage or get_bronze_storage()

    def run(
        self,
        league: str,
        seasons: list[str],
        endpoints: list[str],
        *,
        overwrite: bool = False,
        limit: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> BackfillSummary:
        """Run the backfill across all specified seasons and endpoints."""
        self.storage.ensure_bucket_exists()
        summary = BackfillSummary(seasons=seasons, endpoints=endpoints)

        print("\n" + "=" * 70)
        print(f"Starting Backfill for {league.upper()}")
        print(f"Seasons   ({len(seasons)}): {', '.join(seasons)}")
        print(f"Endpoints ({len(endpoints)}): {', '.join(endpoints)}")
        if limit:
            print(f"Item Limit: {limit} per endpoint")
        if overwrite:
            print("Overwrite : True (re-downloading existing files)")
        print("=" * 70)

        for s_idx, season in enumerate(seasons, 1):
            print(f"\n--- Season [{s_idx}/{len(seasons)}]: {season} ---")

            # Default date range for NBA scoreboards if not provided
            season_start = start_date
            season_end = end_date
            if league == "nba" and (season_start is None or season_end is None):
                season_start, season_end = default_nba_season_dates(season)

            for endpoint in endpoints:
                print(f"  > [{league}:{endpoint}] starting...")
                extractor_cls = get_extractor_class(league, endpoint)
                extractor = extractor_cls(
                    season=season,
                    storage=self.storage,
                    overwrite=overwrite,
                    start=season_start,
                    end=season_end,
                    limit=limit,
                )

                try:
                    res = extractor.run()
                    summary.total_fetched += res.fetched
                    summary.total_skipped += res.skipped
                    summary.total_failed += res.failed
                    summary.endpoint_summaries[f"{season}:{endpoint}"] = res
                    if res.errors:
                        summary.errors.extend(res.errors)

                    print(
                        f"    [{league}:{endpoint}] done -> "
                        f"{res.fetched} fetched, {res.skipped} skipped, {res.failed} failed"
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"    [{league}:{endpoint}] FAILED with exception: {exc}")
                    summary.total_failed += 1
                    summary.errors.append((f"{season}:{endpoint}", str(exc)))

        print("\n" + "=" * 70)
        print("BACKFILL COMPLETED")
        print(f"Total Fetched : {summary.total_fetched}")
        print(f"Total Skipped : {summary.total_skipped}")
        print(f"Total Failed  : {summary.total_failed}")
        if summary.errors:
            print("\nErrors encountered:")
            for key, err in summary.errors[:10]:
                print(f"  - {key}: {err}")
            if len(summary.errors) > 10:
                print(f"  ... and {len(summary.errors) - 10} more errors.")
        print("=" * 70 + "\n")

        return summary
