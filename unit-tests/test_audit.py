"""Unit tests for Bronze layer audit and coverage tooling."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

from basket_app.audit import (
    AuditReport,
    BronzeAuditor,
    CoverageMetric,
    EndpointStats,
    format_bytes,
)


def test_format_bytes():
    assert format_bytes(500) == "500 B"
    assert format_bytes(1024) == "1.0 KB"
    assert format_bytes(1536) == "1.5 KB"
    assert format_bytes(1048576) == "1.0 MB"
    assert format_bytes(1073741824) == "1.0 GB"


def test_parse_key_metadata():
    auditor = BronzeAuditor(storage=MagicMock())

    assert auditor.parse_key_metadata(
        "nba/espn_scoreboard/season=2024-25/date=2024-11-01/scoreboard.json.gz"
    ) == ("nba", "espn_scoreboard", "2024-25")

    assert auditor.parse_key_metadata(
        "euroleague/boxscore/season=E2024/game_code=10/boxscore.json.gz"
    ) == ("euroleague", "boxscore", "E2024")

    assert auditor.parse_key_metadata(
        "nba/player/player_id=4278039/profile.json.gz"
    ) == ("nba", "player", "global")

    assert auditor.parse_key_metadata("_healthcheck/test.json.gz") == (
        "system",
        "_healthcheck",
        "global",
    )


def test_scan_inventory_with_filters():
    mock_storage = MagicMock()
    now = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)
    mock_storage.list_objects.return_value = [
        {
            "key": "euroleague/games/season=E2024/games.json.gz",
            "size": 50000,
            "last_modified": now,
        },
        {
            "key": "euroleague/boxscore/season=E2024/game_code=1/boxscore.json.gz",
            "size": 15000,
            "last_modified": now,
        },
        {
            "key": "euroleague/boxscore/season=E2024/game_code=2/boxscore.json.gz",
            "size": 16000,
            "last_modified": now,
        },
        {
            "key": "nba/teams/season=2024-25/teams.json.gz",
            "size": 7000,
            "last_modified": now,
        },
        {"key": "_healthcheck/check.json.gz", "size": 100, "last_modified": now},
    ]

    auditor = BronzeAuditor(storage=mock_storage)

    # 1. Unfiltered scan
    stats = auditor.scan_inventory()
    assert len(stats) == 3
    # euroleague boxscore should have count 2, size 31000
    el_box = next(s for s in stats if s.endpoint == "boxscore")
    assert el_box.file_count == 2
    assert el_box.total_bytes == 31000

    # 2. Filter by league
    nba_stats = auditor.scan_inventory(league="nba")
    assert len(nba_stats) == 1
    assert nba_stats[0].endpoint == "teams"


def test_audit_euroleague_season():
    mock_storage = MagicMock()
    # Mock games calendar having gameCode 1, 2, 3
    mock_storage.object_exists.side_effect = lambda k: "games" in k or "clubs" in k

    def mock_get_raw_json(k):
        if "games" in k:
            return {
                "data": [
                    {"gameCode": 1, "played": True},
                    {"gameCode": 2, "played": True},
                    {"gameCode": 3, "played": True},
                ]
            }
        if "clubs" in k:
            return {"data": [{"code": "BAR"}, {"code": "RMB"}]}
        return {}

    mock_storage.get_raw_json.side_effect = mock_get_raw_json

    def mock_list_keys(prefix):
        if "boxscore" in prefix:
            return ["euroleague/boxscore/season=E2024/game_code=1/boxscore.json.gz"]
        if "playbyplay" in prefix:
            return [
                "euroleague/playbyplay/season=E2024/game_code=1/playbyplay.json.gz",
                "euroleague/playbyplay/season=E2024/game_code=2/playbyplay.json.gz",
                "euroleague/playbyplay/season=E2024/game_code=3/playbyplay.json.gz",
            ]
        if "shots" in prefix:
            return []
        if "roster" in prefix:
            return ["euroleague/roster/season=E2024/club_code=BAR/roster.json.gz"]
        return []

    mock_storage.list_keys.side_effect = mock_list_keys

    auditor = BronzeAuditor(storage=mock_storage)
    metrics = auditor.audit_euroleague_season("E2024")

    # Check games
    m_games = next(m for m in metrics if m.endpoint == "games")
    assert m_games.status == "COMPLETE"
    assert m_games.coverage_pct == 100.0

    # Check boxscore: 1 found out of 3 expected -> PARTIAL
    m_box = next(m for m in metrics if m.endpoint == "boxscore")
    assert m_box.expected_count == 3
    assert m_box.found_count == 1
    assert m_box.missing_count == 2
    assert m_box.missing_ids == ["2", "3"]
    assert m_box.status == "PARTIAL"

    # Check playbyplay: 3 found out of 3 expected -> COMPLETE
    m_pbp = next(m for m in metrics if m.endpoint == "playbyplay")
    assert m_pbp.expected_count == 3
    assert m_pbp.found_count == 3
    assert m_pbp.coverage_pct == 100.0
    assert m_pbp.status == "COMPLETE"

    # Check shots: 0 found out of 3 expected -> MISSING
    m_shots = next(m for m in metrics if m.endpoint == "shots")
    assert m_shots.found_count == 0
    assert m_shots.status == "MISSING"

    # Check roster: 1 found (BAR) out of 2 expected (BAR, RMB) -> missing RMB
    m_roster = next(m for m in metrics if m.endpoint == "roster")
    assert m_roster.expected_count == 2
    assert m_roster.found_count == 1
    assert m_roster.missing_ids == ["RMB"]


def test_audit_nba_season():
    mock_storage = MagicMock()
    mock_storage.object_exists.side_effect = lambda k: "teams" in k

    def mock_get_raw_json(k):
        if "teams" in k:
            return [{"id": 1}, {"id": 2}]
        if "scoreboard" in k:
            return {"events": [{"id": "1001"}, {"id": "1002"}]}
        return {}

    mock_storage.get_raw_json.side_effect = mock_get_raw_json

    def mock_list_keys(prefix):
        if "roster" in prefix:
            return ["nba/roster/season=2024-25/team_id=1/roster.json.gz"]
        if "espn_scoreboard" in prefix:
            return [
                "nba/espn_scoreboard/season=2024-25/date=2024-11-01/scoreboard.json.gz"
            ]
        if "summary" in prefix:
            return ["nba/summary/season=2024-25/game_id=1001/summary.json.gz"]
        return []

    mock_storage.list_keys.side_effect = mock_list_keys

    auditor = BronzeAuditor(storage=mock_storage)
    metrics = auditor.audit_nba_season("2024-25")

    # Team rosters: 1 found out of 2 expected -> missing team 2
    m_roster = next(m for m in metrics if m.endpoint == "roster")
    assert m_roster.expected_count == 2
    assert m_roster.found_count == 1
    assert m_roster.missing_ids == ["2"]
    assert m_roster.status == "PARTIAL"

    # Summaries: 1 found out of 2 scoreboard games -> missing game 1002
    m_summary = next(m for m in metrics if m.endpoint == "summary")
    assert m_summary.expected_count == 2
    assert m_summary.found_count == 1
    assert m_summary.missing_ids == ["1002"]
    assert m_summary.status == "PARTIAL"


def test_audit_nba_season_with_espn_dict_teams():
    mock_storage = MagicMock()
    mock_storage.object_exists.side_effect = lambda k: "teams" in k

    espn_teams = {
        "sports": [
            {
                "leagues": [
                    {
                        "teams": [
                            {"team": {"id": "1", "name": "Hawks"}},
                            {"team": {"id": "2", "name": "Celtics"}},
                        ]
                    }
                ]
            }
        ]
    }

    mock_storage.get_raw_json.return_value = espn_teams
    mock_storage.list_keys.return_value = [
        "nba/roster/season=2024-25/team_id=1/roster.json.gz"
    ]

    auditor = BronzeAuditor(storage=mock_storage)
    metrics = auditor.audit_nba_season("2024-25")

    m_roster = next(m for m in metrics if m.endpoint == "roster")
    assert m_roster.expected_count == 2
    assert m_roster.found_count == 1
    assert m_roster.missing_ids == ["2"]


def test_audit_report_formatting():
    report = AuditReport(
        generated_at="2026-10-12 10:00:00 UTC",
        inventory=[
            EndpointStats(
                league="nba",
                endpoint="summary",
                season="2024-25",
                file_count=10,
                total_bytes=500000,
                latest_modified="2026-10-12T09:00:00",
            )
        ],
        coverage=[
            CoverageMetric(
                league="nba",
                season="2024-25",
                endpoint="summary",
                expected_count=12,
                found_count=10,
                missing_count=2,
                coverage_pct=83.3,
                status="PARTIAL",
                missing_ids=["401001", "401002"],
            )
        ],
        total_files=10,
        total_bytes=500000,
    )

    text = report.format_text(detailed=True)
    assert "BRONZE LAYER DATA LAKE AUDIT REPORT" in text
    assert "STORAGE INVENTORY" in text
    assert "DATA COVERAGE & COMPLETENESS" in text
    assert "GAPS & MISSING DATA BREAKDOWN" in text
    assert "401001, 401002" in text

    # JSON export
    as_dict = report.to_dict()
    assert as_dict["total_files"] == 10
    assert len(as_dict["coverage"]) == 1
    json_str = report.to_json()
    assert '"total_files": 10' in json_str
