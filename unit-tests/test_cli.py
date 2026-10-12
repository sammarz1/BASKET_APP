"""Unit tests for the CLI entry point."""

from unittest.mock import MagicMock, patch

from basket_app.cli import main
from basket_app.extract.base import ExtractSummary


def test_main_no_args_prints_help(capsys):
    ret = main([])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Basket App ETL & analytics tool" in captured.out


def test_main_extractors_list(capsys):
    ret = main(["extractors"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Available extractors:" in captured.out
    assert "nba/scoreboard" in captured.out


def test_main_extract_list_flag(capsys):
    ret = main(["extract", "--list"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Available extractors:" in captured.out
    assert "euroleague/games" in captured.out


def test_main_extract_missing_args(capsys):
    ret = main(["extract"])
    assert ret == 2
    captured = capsys.readouterr()
    assert "Error: Both 'league' and 'endpoint' are required" in captured.out


def test_main_extract_missing_season(capsys):
    ret = main(["extract", "nba", "scoreboard"])
    assert ret == 2
    captured = capsys.readouterr()
    assert "Error: --season is required" in captured.out


def test_main_list_keys(capsys):
    mock_storage = MagicMock()
    mock_storage.list_keys.return_value = [
        "nba/schedule/season=2024-25/schedule.json.gz"
    ]

    with patch("basket_app.cli.get_bronze_storage", return_value=mock_storage):
        ret = main(["list", "nba/"])

    assert ret == 0
    captured = capsys.readouterr()
    assert "nba/schedule/season=2024-25/schedule.json.gz" in captured.out


def test_main_extract_success(capsys):
    mock_storage = MagicMock()
    mock_extractor = MagicMock()
    mock_extractor.run.return_value = ExtractSummary(fetched=1, skipped=0, failed=0)

    with patch("basket_app.cli.get_bronze_storage", return_value=mock_storage):
        with patch(
            "basket_app.cli.get_extractor_class",
            return_value=MagicMock(return_value=mock_extractor),
        ):
            ret = main(["extract", "nba", "schedule", "--season", "2024-25"])

    assert ret == 0
    mock_storage.ensure_bucket_exists.assert_called_once()
    mock_extractor.run.assert_called_once()
    captured = capsys.readouterr()
    assert "Extraction complete: 1 fetched, 0 skipped, 0 failed." in captured.out


def test_main_audit(capsys):
    mock_auditor = MagicMock()
    mock_report = MagicMock()
    mock_report.format_text.return_value = "AUDIT OUTPUT TEXT"
    mock_report.to_json.return_value = '{"status": "ok"}'
    mock_auditor.run_audit.return_value = mock_report

    with patch("basket_app.cli.BronzeAuditor", return_value=mock_auditor):
        ret = main(["audit", "--league", "nba"])

    assert ret == 0
    mock_auditor.run_audit.assert_called_once_with(league="nba", season=None)
    captured = capsys.readouterr()
    assert "AUDIT OUTPUT TEXT" in captured.out
