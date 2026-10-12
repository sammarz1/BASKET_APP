"""Audit and coverage inspection tooling for Bronze layer data lakehouse."""

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional

from basket_app.core.storage import BronzeStorage, get_bronze_storage


def format_bytes(num_bytes: int) -> str:
    """Format a byte count into a human-readable string."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    for unit in ("KB", "MB", "GB", "TB"):
        num_bytes /= 1024.0
        if num_bytes < 1024.0 or unit == "TB":
            return f"{num_bytes:.1f} {unit}"
    return f"{num_bytes:.1f} TB"


@dataclass
class EndpointStats:
    """Storage statistics for a specific (league, endpoint, season) partition."""

    league: str
    endpoint: str
    season: str
    file_count: int = 0
    total_bytes: int = 0
    latest_modified: Optional[str] = None


@dataclass
class CoverageMetric:
    """Audit coverage metrics for an endpoint within a season."""

    league: str
    season: str
    endpoint: str
    expected_count: int
    found_count: int
    missing_count: int
    coverage_pct: float
    status: str  # "COMPLETE", "PARTIAL", "MISSING", "N/A"
    missing_ids: list[str] = field(default_factory=list)


@dataclass
class AuditReport:
    """Comprehensive audit report for storage inventory and data coverage."""

    generated_at: str
    inventory: list[EndpointStats] = field(default_factory=list)
    coverage: list[CoverageMetric] = field(default_factory=list)
    total_files: int = 0
    total_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert report to serializable dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Convert report to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def format_text(self, detailed: bool = False) -> str:
        """Format report into human-readable terminal output."""
        lines: list[str] = []
        lines.append("=" * 80)
        lines.append(f"  BRONZE LAYER DATA LAKE AUDIT REPORT  [{self.generated_at}]")
        lines.append("=" * 80)
        lines.append("")

        # Section 1: Storage Inventory
        lines.append("── STORAGE INVENTORY ──────────────────────────────────────────")
        lines.append(
            f"{'League':<12} {'Endpoint':<16} {'Season':<10} {'Files':>8} {'Size':>12} {'Latest Modified':<20}"
        )
        lines.append("-" * 80)
        for stat in self.inventory:
            latest = stat.latest_modified[:19] if stat.latest_modified else "-"
            size_str = format_bytes(stat.total_bytes)
            lines.append(
                f"{stat.league:<12} {stat.endpoint:<16} {stat.season:<10} {stat.file_count:>8d} {size_str:>12} {latest:<20}"
            )
        lines.append("-" * 80)
        lines.append(
            f"Total stored: {self.total_files} files across Bronze ({format_bytes(self.total_bytes)})"
        )
        lines.append("")

        # Section 2: Coverage & Completeness
        if self.coverage:
            lines.append(
                "── DATA COVERAGE & COMPLETENESS ───────────────────────────────"
            )
            lines.append(
                f"{'League':<12} {'Season':<10} {'Endpoint':<16} {'Expected':>9} {'Found':>7} {'Missing':>8} {'Coverage':>9} {'Status':<10}"
            )
            lines.append("-" * 84)
            for cov in self.coverage:
                cov_str = f"{cov.coverage_pct:.1f}%"
                lines.append(
                    f"{cov.league:<12} {cov.season:<10} {cov.endpoint:<16} {cov.expected_count:>9d} {cov.found_count:>7d} {cov.missing_count:>8d} {cov_str:>9} {cov.status:<10}"
                )
            lines.append("-" * 84)
            lines.append("")

        # Section 3: Missing Items Detail
        missing_entries = [c for c in self.coverage if c.missing_ids]
        if missing_entries:
            lines.append(
                "── GAPS & MISSING DATA BREAKDOWN ──────────────────────────────"
            )
            for cov in missing_entries:
                sample_count = len(cov.missing_ids)
                lines.append(
                    f"• {cov.league.upper()} {cov.season} [{cov.endpoint}]: {sample_count} missing"
                )
                if detailed or sample_count <= 10:
                    lines.append(f"  Missing IDs: {', '.join(cov.missing_ids[:25])}")
                    if sample_count > 25:
                        lines.append(f"  ... and {sample_count - 25} more")
                else:
                    preview = ", ".join(cov.missing_ids[:8])
                    lines.append(
                        f"  Sample missing IDs: {preview} ... (run with --detailed to view all {sample_count})"
                    )
            lines.append("")

        return "\n".join(lines)


class BronzeAuditor:
    """Audits data coverage, storage footprints, and data gaps in the Bronze layer."""

    def __init__(self, storage: Optional[BronzeStorage] = None):
        self.storage = storage or get_bronze_storage()

    def parse_key_metadata(self, key: str) -> tuple[str, str, str]:
        """Extract (league, endpoint, season) from an S3 key.

        Example:
            'nba/espn_scoreboard/season=2024-25/date=2024-11-01/scoreboard.json.gz'
            -> ('nba', 'espn_scoreboard', '2024-25')
        """
        parts = key.split("/")
        if len(parts) < 2 or parts[0].startswith("_"):
            return ("system", parts[0], "global")

        league = parts[0]
        endpoint = parts[1]
        season = "global"

        for p in parts[2:]:
            if p.startswith("season="):
                season = p.split("=", 1)[1]
                break

        return (league, endpoint, season)

    def scan_inventory(
        self, league: Optional[str] = None, season: Optional[str] = None
    ) -> list[EndpointStats]:
        """Scan Bronze storage and aggregate file counts, sizes, and timestamps."""
        prefix = f"{league}/" if league else ""
        raw_objects = self.storage.list_objects(prefix=prefix)

        grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
        for obj in raw_objects:
            key = obj["key"]
            if key.startswith("_healthcheck"):
                continue

            l, ep, s = self.parse_key_metadata(key)
            if league and l != league:
                continue
            if season and s != season and s != "global":
                continue

            group_key = (l, ep, s)
            if group_key not in grouped:
                grouped[group_key] = {
                    "count": 0,
                    "bytes": 0,
                    "latest": None,
                }

            grouped[group_key]["count"] += 1
            grouped[group_key]["bytes"] += obj.get("size", 0)

            mod = obj.get("last_modified")
            if mod:
                mod_iso = mod.isoformat() if hasattr(mod, "isoformat") else str(mod)
                curr = grouped[group_key]["latest"]
                if curr is None or mod_iso > curr:
                    grouped[group_key]["latest"] = mod_iso

        stats: list[EndpointStats] = []
        for (l, ep, s), data in sorted(grouped.items()):
            stats.append(
                EndpointStats(
                    league=l,
                    endpoint=ep,
                    season=s,
                    file_count=data["count"],
                    total_bytes=data["bytes"],
                    latest_modified=data["latest"],
                )
            )
        return stats

    def audit_euroleague_season(self, season: str) -> list[CoverageMetric]:
        """Verify completeness of EuroLeague data for a given season."""
        metrics: list[CoverageMetric] = []

        # 1. Games calendar
        games_key = f"euroleague/games/season={season}/games.json.gz"
        expected_game_codes: list[int] = []
        has_games = self.storage.object_exists(games_key)
        if has_games:
            try:
                games_data = self.storage.get_raw_json(games_key)
                g_list = (
                    games_data.get("data", [])
                    if isinstance(games_data, dict)
                    else games_data
                )
                expected_game_codes = [
                    g["gameCode"]
                    for g in g_list
                    if g.get("played", True) and "gameCode" in g
                ]
            except Exception:
                expected_game_codes = []

        metrics.append(
            CoverageMetric(
                league="euroleague",
                season=season,
                endpoint="games",
                expected_count=1,
                found_count=1 if has_games else 0,
                missing_count=0 if has_games else 1,
                coverage_pct=100.0 if has_games else 0.0,
                status="COMPLETE" if has_games else "MISSING",
            )
        )

        # 2. Game-dependent endpoints: boxscore, playbyplay, shots
        game_endpoints = [
            ("boxscore", "boxscore", re.compile(r"game_code=(\d+)")),
            ("playbyplay", "playbyplay", re.compile(r"game_code=(\d+)")),
            ("shots", "shots", re.compile(r"game_code=(\d+)")),
        ]

        for ep_name, prefix_sub, pattern in game_endpoints:
            prefix = f"euroleague/{prefix_sub}/season={season}/"
            stored_keys = self.storage.list_keys(prefix)
            found_codes: set[int] = set()
            for k in stored_keys:
                m = pattern.search(k)
                if m:
                    found_codes.add(int(m.group(1)))

            if expected_game_codes:
                expected_set = set(expected_game_codes)
                missing = sorted(list(expected_set - found_codes))
                found_exp = len(found_codes & expected_set)
                exp_cnt = len(expected_set)
                pct = (found_exp / exp_cnt * 100.0) if exp_cnt > 0 else 0.0
                status = (
                    "COMPLETE"
                    if pct == 100.0
                    else ("PARTIAL" if pct > 0 else "MISSING")
                )
            else:
                missing = []
                exp_cnt = len(found_codes)
                found_exp = len(found_codes)
                pct = 100.0 if found_exp > 0 else 0.0
                status = "COMPLETE" if found_exp > 0 else "N/A"

            metrics.append(
                CoverageMetric(
                    league="euroleague",
                    season=season,
                    endpoint=ep_name,
                    expected_count=exp_cnt,
                    found_count=found_exp,
                    missing_count=len(missing),
                    coverage_pct=pct,
                    status=status,
                    missing_ids=[str(code) for code in missing],
                )
            )

        # 3. Clubs and Rosters
        clubs_key = f"euroleague/clubs/season={season}/clubs.json.gz"
        has_clubs = self.storage.object_exists(clubs_key)
        expected_club_codes: list[str] = []
        if has_clubs:
            try:
                clubs_data = self.storage.get_raw_json(clubs_key)
                c_list = (
                    clubs_data.get("data", [])
                    if isinstance(clubs_data, dict)
                    else clubs_data
                )
                expected_club_codes = [c["code"] for c in c_list if "code" in c]
            except Exception:
                expected_club_codes = []

        metrics.append(
            CoverageMetric(
                league="euroleague",
                season=season,
                endpoint="clubs",
                expected_count=1,
                found_count=1 if has_clubs else 0,
                missing_count=0 if has_clubs else 1,
                coverage_pct=100.0 if has_clubs else 0.0,
                status="COMPLETE" if has_clubs else "MISSING",
            )
        )

        # Rosters coverage
        roster_keys = self.storage.list_keys(f"euroleague/roster/season={season}/")
        roster_pattern = re.compile(r"club_code=([^/]+)")
        found_roster_clubs: set[str] = set()
        for k in roster_keys:
            m = roster_pattern.search(k)
            if m:
                found_roster_clubs.add(m.group(1))

        if expected_club_codes:
            exp_clubs_set = set(expected_club_codes)
            missing_clubs = sorted(list(exp_clubs_set - found_roster_clubs))
            found_exp_clubs = len(found_roster_clubs & exp_clubs_set)
            exp_clubs_cnt = len(exp_clubs_set)
            club_pct = (
                (found_exp_clubs / exp_clubs_cnt * 100.0) if exp_clubs_cnt > 0 else 0.0
            )
            club_status = (
                "COMPLETE"
                if club_pct == 100.0
                else ("PARTIAL" if club_pct > 0 else "MISSING")
            )
        else:
            missing_clubs = []
            exp_clubs_cnt = len(found_roster_clubs)
            found_exp_clubs = len(found_roster_clubs)
            club_pct = 100.0 if found_exp_clubs > 0 else 0.0
            club_status = "COMPLETE" if found_exp_clubs > 0 else "N/A"

        metrics.append(
            CoverageMetric(
                league="euroleague",
                season=season,
                endpoint="roster",
                expected_count=exp_clubs_cnt,
                found_count=found_exp_clubs,
                missing_count=len(missing_clubs),
                coverage_pct=club_pct,
                status=club_status,
                missing_ids=missing_clubs,
            )
        )

        # 4. Standings & People
        for ep in ("standings", "people"):
            key = f"euroleague/{ep}/season={season}/{ep}.json.gz"
            exists = self.storage.object_exists(key)
            metrics.append(
                CoverageMetric(
                    league="euroleague",
                    season=season,
                    endpoint=ep,
                    expected_count=1,
                    found_count=1 if exists else 0,
                    missing_count=0 if exists else 1,
                    coverage_pct=100.0 if exists else 0.0,
                    status="COMPLETE" if exists else "MISSING",
                )
            )

        return metrics

    def audit_nba_season(self, season: str) -> list[CoverageMetric]:
        """Verify completeness of NBA data for a given season."""
        metrics: list[CoverageMetric] = []

        # 1. Teams
        teams_key = f"nba/teams/season={season}/teams.json.gz"
        has_teams = self.storage.object_exists(teams_key)
        expected_team_ids: list[str] = []
        if has_teams:
            try:
                teams_data = self.storage.get_raw_json(teams_key)
                expected_team_ids = [
                    str(t.get("id")) for t in teams_data if t.get("id")
                ]
            except Exception:
                expected_team_ids = []

        metrics.append(
            CoverageMetric(
                league="nba",
                season=season,
                endpoint="teams",
                expected_count=1,
                found_count=1 if has_teams else 0,
                missing_count=0 if has_teams else 1,
                coverage_pct=100.0 if has_teams else 0.0,
                status="COMPLETE" if has_teams else "MISSING",
            )
        )

        # 2. Team Rosters
        roster_keys = self.storage.list_keys(f"nba/roster/season={season}/")
        roster_pattern = re.compile(r"team_id=(\d+)")
        found_roster_teams: set[str] = set()
        for k in roster_keys:
            m = roster_pattern.search(k)
            if m:
                found_roster_teams.add(m.group(1))

        # NBA has 30 teams
        expected_roster_cnt = len(expected_team_ids) if expected_team_ids else 30
        if expected_team_ids:
            exp_teams_set = set(expected_team_ids)
            missing_teams = sorted(list(exp_teams_set - found_roster_teams))
            found_exp_teams = len(found_roster_teams & exp_teams_set)
        else:
            missing_teams = []
            found_exp_teams = len(found_roster_teams)

        roster_pct = (
            (found_exp_teams / expected_roster_cnt * 100.0)
            if expected_roster_cnt > 0
            else 0.0
        )
        roster_status = (
            "COMPLETE"
            if roster_pct == 100.0
            else ("PARTIAL" if roster_pct > 0 else "MISSING")
        )

        metrics.append(
            CoverageMetric(
                league="nba",
                season=season,
                endpoint="roster",
                expected_count=expected_roster_cnt,
                found_count=found_exp_teams,
                missing_count=(
                    len(missing_teams)
                    if expected_team_ids
                    else max(0, expected_roster_cnt - found_exp_teams)
                ),
                coverage_pct=roster_pct,
                status=roster_status,
                missing_ids=missing_teams,
            )
        )

        # 3. Scoreboard & Game Summaries
        scoreboard_keys = self.storage.list_keys(
            f"nba/espn_scoreboard/season={season}/"
        )
        scoreboard_game_ids: list[str] = []
        for sb_key in scoreboard_keys:
            try:
                data = self.storage.get_raw_json(sb_key)
                for ev in data.get("events", []):
                    ev_id = str(ev.get("id", ""))
                    if ev_id and ev_id not in scoreboard_game_ids:
                        scoreboard_game_ids.append(ev_id)
            except Exception:
                continue

        summary_keys = self.storage.list_keys(f"nba/summary/season={season}/")
        summary_pattern = re.compile(r"game_id=(\d+)")
        found_summary_ids: set[str] = set()
        for k in summary_keys:
            m = summary_pattern.search(k)
            if m:
                found_summary_ids.add(m.group(1))

        if scoreboard_game_ids:
            exp_games_set = set(scoreboard_game_ids)
            missing_summaries = sorted(list(exp_games_set - found_summary_ids))
            found_exp_sum = len(found_summary_ids & exp_games_set)
            exp_sum_cnt = len(exp_games_set)
            sum_pct = (found_exp_sum / exp_sum_cnt * 100.0) if exp_sum_cnt > 0 else 0.0
            sum_status = (
                "COMPLETE"
                if sum_pct == 100.0
                else ("PARTIAL" if sum_pct > 0 else "MISSING")
            )
        else:
            missing_summaries = []
            exp_sum_cnt = len(found_summary_ids)
            found_exp_sum = len(found_summary_ids)
            sum_pct = 100.0 if found_exp_sum > 0 else 0.0
            sum_status = "COMPLETE" if found_exp_sum > 0 else "N/A"

        metrics.append(
            CoverageMetric(
                league="nba",
                season=season,
                endpoint="summary",
                expected_count=exp_sum_cnt,
                found_count=found_exp_sum,
                missing_count=len(missing_summaries),
                coverage_pct=sum_pct,
                status=sum_status,
                missing_ids=missing_summaries,
            )
        )

        # 4. Standings
        standings_key = f"nba/standings/season={season}/standings.json.gz"
        has_standings = self.storage.object_exists(standings_key)
        metrics.append(
            CoverageMetric(
                league="nba",
                season=season,
                endpoint="standings",
                expected_count=1,
                found_count=1 if has_standings else 0,
                missing_count=0 if has_standings else 1,
                coverage_pct=100.0 if has_standings else 0.0,
                status="COMPLETE" if has_standings else "MISSING",
            )
        )

        return metrics

    def run_audit(
        self,
        league: Optional[str] = None,
        season: Optional[str] = None,
    ) -> AuditReport:
        """Run full inventory and coverage audit across the data lakehouse."""
        inventory = self.scan_inventory(league=league, season=season)
        total_files = sum(s.file_count for s in inventory)
        total_bytes = sum(s.total_bytes for s in inventory)

        # Discover distinct seasons per league
        discovered_seasons: dict[str, set[str]] = {}
        for s in inventory:
            if s.league in ("nba", "euroleague") and s.season != "global":
                discovered_seasons.setdefault(s.league, set()).add(s.season)

        # If user explicitly passed season, ensure it's audited
        if season:
            if league:
                discovered_seasons.setdefault(league, set()).add(season)
            else:
                for lg in ("nba", "euroleague"):
                    discovered_seasons.setdefault(lg, set()).add(season)

        coverage: list[CoverageMetric] = []
        # Audit EuroLeague seasons
        if not league or league == "euroleague":
            for s_code in sorted(discovered_seasons.get("euroleague", [])):
                if season and s_code != season:
                    continue
                coverage.extend(self.audit_euroleague_season(s_code))

        # Audit NBA seasons
        if not league or league == "nba":
            for s_code in sorted(discovered_seasons.get("nba", [])):
                if season and s_code != season:
                    continue
                coverage.extend(self.audit_nba_season(s_code))

        return AuditReport(
            generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            inventory=inventory,
            coverage=coverage,
            total_files=total_files,
            total_bytes=total_bytes,
        )
