"""Unit tests for the backfill orchestrator and CLI."""

from unittest.mock import MagicMock, patch
import pytest

from basket_app.backfill import (
    BackfillOrchestrator,
    BackfillSummary,
    default_nba_season_dates,
    parse_season_range,
    resolve_endpoints,
)
from basket_app.cli import main
from basket_app.extract.base import ExtractSummary


def test_parse_season_range_euroleague():
    seasons = parse_season_range("euroleague", "E2020", "E2023")
    assert seasons == ["E2020", "E2021", "E2022", "E2023"]

    eurocup = parse_season_range("euroleague", "U2021", "U2022")
    assert eurocup == ["U2021", "U2022"]


def test_parse_season_range_euroleague_invalid():
    with pytest.raises(ValueError, match="Season prefixes must match"):
        parse_season_range("euroleague", "E2020", "U2022")

    with pytest.raises(ValueError, match="is after end season"):
        parse_season_range("euroleague", "E2024", "E2020")


def test_parse_season_range_nba():
    seasons = parse_season_range("nba", "2021-22", "2023-24")
    assert seasons == ["2021-22", "2022-23", "2023-24"]


def test_parse_season_range_nba_invalid():
    with pytest.raises(ValueError, match="is after end season"):
        parse_season_range("nba", "2025-26", "2022-23")


def test_resolve_endpoints_defaults():
    el = resolve_endpoints("euroleague")
    assert el[0] == "games"
    assert "boxscore" in el
    assert "roster" in el

    nba = resolve_endpoints("nba")
    assert nba[0] == "teams"
    assert "scoreboard" in nba
    assert "summary" in nba


def test_resolve_endpoints_filtering():
    # Maintains dependency order regardless of include ordering
    filtered = resolve_endpoints("euroleague", include=["shots", "games", "clubs"])
    assert filtered == ["games", "clubs", "shots"]

    excluded = resolve_endpoints("euroleague", exclude=["shots", "pbp"])
    assert "shots" not in excluded
    assert "pbp" not in excluded
    assert "games" in excluded


def test_resolve_endpoints_unknown():
    with pytest.raises(ValueError, match="Unknown endpoint"):
        resolve_endpoints("euroleague", include=["fake_endpoint"])


def test_default_nba_season_dates():
    start, end = default_nba_season_dates("2024-25")
    assert start.year == 2024 and start.month == 10
    assert end.year == 2025 and end.month == 6


def test_backfill_orchestrator_run():
    mock_storage = MagicMock()
    orchestrator = BackfillOrchestrator(storage=mock_storage)

    mock_extractor = MagicMock()
    mock_extractor.run.return_value = ExtractSummary(fetched=5, skipped=2, failed=0)

    with patch(
        "basket_app.backfill.get_extractor_class",
        return_value=MagicMock(return_value=mock_extractor),
    ):
        summary = orchestrator.run(
            league="euroleague",
            seasons=["E2023", "E2024"],
            endpoints=["games", "clubs"],
        )

    assert summary.total_fetched == 20  # 4 runs * 5
    assert summary.total_skipped == 8  # 4 runs * 2
    assert summary.total_failed == 0
    assert len(summary.seasons) == 2


def test_cli_backfill_missing_seasons(capsys):
    ret = main(["backfill", "euroleague"])
    assert ret == 2
    captured = capsys.readouterr()
    assert (
        "Either --season or both --start-season and --end-season are required"
        in captured.out
    )


def test_cli_backfill_invalid_range(capsys):
    ret = main(
        ["backfill", "euroleague", "--start-season", "E2025", "--end-season", "E2020"]
    )
    assert ret == 2
    captured = capsys.readouterr()
    assert "Error parsing season range" in captured.out


def test_cli_backfill_success():
    with patch(
        "basket_app.cli.BackfillOrchestrator.run",
        return_value=BackfillSummary(total_failed=0),
    ) as mock_run:
        ret = main(
            ["backfill", "euroleague", "--season", "E2024", "--include", "games,clubs"]
        )

    assert ret == 0
    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["seasons"] == ["E2024"]
    assert mock_run.call_args.kwargs["endpoints"] == ["games", "clubs"]
