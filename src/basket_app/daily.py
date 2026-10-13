"""Daily operational ingestion runner for ongoing basketball seasons."""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import logging
from typing import Optional

from basket_app.core.http import HttpClient
from basket_app.core.storage import BronzeStorage, get_bronze_storage
from basket_app.extract.registry import get_extractor_class

log = logging.getLogger(__name__)


def current_season(league: str, for_date: Optional[date] = None) -> str:
    """Infer the current season identifier based on calendar date."""
    d = for_date or datetime.now(timezone.utc).date()
    league = league.lower().strip()

    if league == "nba":
        # NBA season starts in October; games Jan-June belong to previous calendar year's season
        year = d.year if d.month >= 10 else d.year - 1
        return f"{year}-{str(year + 1)[2:]}"

    if league == "euroleague":
        # EuroLeague calendar begins in July/August
        year = d.year if d.month >= 7 else d.year - 1
        return f"E{year}"

    raise ValueError(f"Unknown league: {league}")


@dataclass
class DailySummary:
    """Summary of a daily ingestion run."""

    target_dates: list[date] = field(default_factory=list)
    leagues: list[str] = field(default_factory=list)
    total_fetched: int = 0
    total_skipped: int = 0
    total_failed: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)


class DailyRunner:
    """Orchestrates daily operational catch-up ingestion for active seasons."""

    def __init__(
        self,
        storage: Optional[BronzeStorage] = None,
        client: Optional[HttpClient] = None,
    ):
        self.storage = storage or get_bronze_storage()
        self.client = client or HttpClient()

    def run(
        self,
        league: Optional[str] = None,
        target_date: Optional[date] = None,
        days_back: int = 1,
        season: Optional[str] = None,
        refresh_rosters: bool = False,
    ) -> DailySummary:
        """Run daily ingestion for target date(s)."""
        self.storage.ensure_bucket_exists()

        end_d = target_date or (datetime.now(timezone.utc).date() - timedelta(days=1))
        start_d = end_d - timedelta(days=days_back - 1)

        dates = []
        cur = start_d
        while cur <= end_d:
            dates.append(cur)
            cur += timedelta(days=1)

        leagues_to_run = [league.lower().strip()] if league else ["euroleague", "nba"]

        summary = DailySummary(target_dates=dates, leagues=leagues_to_run)

        print("\n" + "=" * 70)
        print("DAILY OPERATIONAL INGESTION")
        print(f"Date Range : {dates[0]} to {dates[-1]} ({len(dates)} day(s))")
        print(f"Leagues    : {', '.join(leagues_to_run)}")
        print("=" * 70)

        for lg in leagues_to_run:
            lg_season = season or current_season(lg, for_date=end_d)
            print(f"\n--- {lg.upper()} (Season: {lg_season}) ---")

            if lg == "nba":
                self._run_nba_daily(lg_season, start_d, end_d, summary, refresh_rosters)
            elif lg == "euroleague":
                self._run_euroleague_daily(lg_season, summary, refresh_rosters)

        print("\n" + "=" * 70)
        print("DAILY INGESTION COMPLETED")
        print(f"Total Fetched : {summary.total_fetched}")
        print(f"Total Skipped : {summary.total_skipped}")
        print(f"Total Failed  : {summary.total_failed}")
        if summary.errors:
            print("\nErrors encountered:")
            for key, err in summary.errors:
                print(f"  - {key}: {err}")
        print("=" * 70 + "\n")

        return summary

    def _run_nba_daily(
        self,
        season: str,
        start_d: date,
        end_d: date,
        summary: DailySummary,
        refresh_rosters: bool,
    ) -> None:
        """Execute daily NBA ingestion sequence."""
        # 1. Scoreboards for the target dates
        self._execute_step(
            "nba",
            "scoreboard",
            season,
            summary,
            start=start_d,
            end=end_d,
            overwrite=True,  # Refresh scoreboards to catch final scores
        )

        # 2. Game summaries for games on those dates
        self._execute_step(
            "nba",
            "summary",
            season,
            summary,
            start=start_d,
            end=end_d,
            overwrite=False,  # Skip already fetched completed games
        )

        # 3. Always refresh current Standings
        self._execute_step(
            "nba",
            "standings",
            season,
            summary,
            overwrite=True,
        )

        # 4. Optionally refresh Rosters
        if refresh_rosters:
            self._execute_step(
                "nba",
                "roster",
                season,
                summary,
                overwrite=True,
            )

    def _run_euroleague_daily(
        self,
        season: str,
        summary: DailySummary,
        refresh_rosters: bool,
    ) -> None:
        """Execute daily EuroLeague ingestion sequence."""
        # 1. Refresh calendar games (to pick up played status)
        self._execute_step(
            "euroleague",
            "games",
            season,
            summary,
            overwrite=True,
        )

        # 2. Boxscores for newly completed games
        self._execute_step(
            "euroleague",
            "boxscore",
            season,
            summary,
            overwrite=False,
        )

        # 3. Play-by-play for newly completed games
        self._execute_step(
            "euroleague",
            "pbp",
            season,
            summary,
            overwrite=False,
        )

        # 4. Shot charts for newly completed games
        self._execute_step(
            "euroleague",
            "shots",
            season,
            summary,
            overwrite=False,
        )

        # 5. Refresh Standings
        self._execute_step(
            "euroleague",
            "standings",
            season,
            summary,
            overwrite=True,
        )

        # 6. Optionally refresh Rosters & People
        if refresh_rosters:
            self._execute_step(
                "euroleague",
                "roster",
                season,
                summary,
                overwrite=True,
            )
            self._execute_step(
                "euroleague",
                "people",
                season,
                summary,
                overwrite=True,
            )

    def _execute_step(
        self,
        league: str,
        endpoint: str,
        season: str,
        summary: DailySummary,
        *,
        start: Optional[date] = None,
        end: Optional[date] = None,
        overwrite: bool = False,
    ) -> None:
        print(f"  > [{league}:{endpoint}]...")
        try:
            extractor_cls = get_extractor_class(league, endpoint)
            extractor = extractor_cls(
                season=season,
                storage=self.storage,
                client=self.client,
                overwrite=overwrite,
                start=start,
                end=end,
            )
            res = extractor.run()
            summary.total_fetched += res.fetched
            summary.total_skipped += res.skipped
            summary.total_failed += res.failed
            if res.errors:
                summary.errors.extend(res.errors)
            print(
                f"    [{league}:{endpoint}] -> "
                f"{res.fetched} fetched, {res.skipped} skipped, {res.failed} failed"
            )
        except Exception as exc:  # noqa: BLE001
            print(f"    [{league}:{endpoint}] FAILED: {exc}")
            summary.total_failed += 1
            summary.errors.append((f"{league}:{endpoint}", str(exc)))
