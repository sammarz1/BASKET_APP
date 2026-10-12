"""Unit tests for the daily operational runner."""

from datetime import date
from unittest.mock import MagicMock, patch
import pytest

from basket_app.cli import main
from basket_app.daily import DailyRunner, DailySummary, current_season
from basket_app.extract.base import ExtractSummary


def test_current_season_nba():
    assert current_season("nba", date(2024, 10, 15)) == "2024-25"
    assert current_season("nba", date(2025, 1, 10)) == "2024-25"
    assert current_season("nba", date(2025, 6, 20)) == "2024-25"
    assert current_season("nba", date(2025, 11, 1)) == "2025-26"


def test_current_season_euroleague():
    assert current_season("euroleague", date(2024, 10, 1)) == "E2024"
    assert current_season("euroleague", date(2025, 2, 15)) == "E2024"
    assert current_season("euroleague", date(2025, 5, 25)) == "E2024"
    assert current_season("euroleague", date(2025, 8, 1)) == "E2025"


def test_current_season_unknown():
    with pytest.raises(ValueError, match="Unknown league"):
        current_season("fake_league")


def test_daily_runner_run():
    mock_storage = MagicMock()
    runner = DailyRunner(storage=mock_storage)

    mock_extractor = MagicMock()
    mock_extractor.run.return_value = ExtractSummary(fetched=2, skipped=1, failed=0)

    with patch(
        "basket_app.daily.get_extractor_class",
        return_value=MagicMock(return_value=mock_extractor),
    ):
        summary = runner.run(
            league="nba",
            target_date=date(2024, 11, 2),
            days_back=2,
            season="2024-25",
        )

    assert summary.total_fetched == 6  # 3 steps * 2
    assert summary.total_skipped == 3  # 3 steps * 1
    assert summary.total_failed == 0
    assert summary.target_dates == [date(2024, 11, 1), date(2024, 11, 2)]


def test_cli_daily_command():
    with patch(
        "basket_app.cli.DailyRunner.run",
        return_value=DailySummary(total_failed=0),
    ) as mock_run:
        ret = main(
            [
                "daily",
                "--league",
                "nba",
                "--season",
                "2024-25",
                "--date",
                "2024-11-01",
            ]
        )

    assert ret == 0
    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["league"] == "nba"
    assert mock_run.call_args.kwargs["season"] == "2024-25"
    assert mock_run.call_args.kwargs["target_date"] == date(2024, 11, 1)
