"""Command-line entry point.

Examples:
    python -m basket_app extract nba scoreboard --season 2024-25 --start 2024-11-01 --end 2024-11-05
    python -m basket_app extract euroleague games --season E2024
    python -m basket_app backfill euroleague --season E2024 --include games,clubs
    python -m basket_app backfill nba --start-season 2022-23 --end-season 2024-25
    python -m basket_app daily
    python -m basket_app list nba/
    python -m basket_app extractors
"""

import argparse
import logging
from datetime import date

from basket_app.audit import BronzeAuditor
from basket_app.backfill import (
    BackfillOrchestrator,
    parse_season_range,
    resolve_endpoints,
)
from basket_app.core.config import get_settings
from basket_app.core.storage import get_bronze_storage
from basket_app.daily import DailyRunner
from basket_app.extract.registry import (
    get_extractor_class,
    list_available_extractors,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="basket_app", description="Basket App ETL & analytics tool"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    sub = parser.add_subparsers(dest="command")

    # extract subcommand
    extract = sub.add_parser("extract", help="Fetch raw data into Bronze storage")
    extract.add_argument("league", nargs="?", help="League name (e.g. nba, euroleague)")
    extract.add_argument(
        "endpoint",
        nargs="?",
        help="Endpoint name (e.g. scoreboard, games, schedule)",
    )
    extract.add_argument(
        "--season",
        help="Season identifier (NBA: '2024-25', EuroLeague: 'E2024')",
    )
    extract.add_argument(
        "--start",
        type=date.fromisoformat,
        help="Start date YYYY-MM-DD (date-partitioned endpoints)",
    )
    extract.add_argument(
        "--end",
        type=date.fromisoformat,
        help="End date YYYY-MM-DD inclusive",
    )
    extract.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-fetch and overwrite objects that already exist in bronze",
    )
    extract.add_argument(
        "--limit",
        type=int,
        help="Max number of items to process (useful for testing)",
    )
    extract.add_argument(
        "--list",
        action="store_true",
        help="List all registered extractors",
    )

    # backfill subcommand
    backfill_p = sub.add_parser(
        "backfill", help="Bulk backfill multiple endpoints and seasons"
    )
    backfill_p.add_argument(
        "league", choices=["nba", "euroleague"], help="League to backfill"
    )
    backfill_p.add_argument(
        "--season",
        help="Single season to backfill (e.g. '2024-25', 'E2024')",
    )
    backfill_p.add_argument(
        "--start-season",
        help="First season in range (e.g. '2020-21', 'E2020')",
    )
    backfill_p.add_argument(
        "--end-season",
        help="Last season in range inclusive (e.g. '2024-25', 'E2024')",
    )
    backfill_p.add_argument(
        "--start",
        type=date.fromisoformat,
        help="Start date YYYY-MM-DD for date-partitioned scoreboards",
    )
    backfill_p.add_argument(
        "--end",
        type=date.fromisoformat,
        help="End date YYYY-MM-DD for date-partitioned scoreboards",
    )
    backfill_p.add_argument(
        "--include",
        help="Comma-separated endpoints to include (e.g. 'games,boxscore')",
    )
    backfill_p.add_argument(
        "--exclude",
        help="Comma-separated endpoints to exclude (e.g. 'shots,pbp')",
    )
    backfill_p.add_argument(
        "--limit",
        type=int,
        help="Max items per endpoint (useful for testing)",
    )
    backfill_p.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-fetch and overwrite objects that already exist in bronze",
    )

    # daily subcommand
    daily_p = sub.add_parser(
        "daily", help="Run daily operational ingestion for active seasons"
    )
    daily_p.add_argument(
        "--league",
        choices=["nba", "euroleague"],
        help="Optional league filter (runs both if omitted)",
    )
    daily_p.add_argument(
        "--date",
        type=date.fromisoformat,
        help="Target date YYYY-MM-DD (defaults to yesterday)",
    )
    daily_p.add_argument(
        "--days-back",
        type=int,
        default=1,
        help="Number of days back to catch up (default: 1)",
    )
    daily_p.add_argument(
        "--season",
        help="Override season code (auto-inferred if omitted)",
    )
    daily_p.add_argument(
        "--refresh-rosters",
        action="store_true",
        help="Also refresh team rosters and personnel",
    )

    # audit subcommand
    audit_p = sub.add_parser(
        "audit", help="Audit Bronze lakehouse storage and coverage completeness"
    )
    audit_p.add_argument(
        "--league", choices=["nba", "euroleague"], help="Filter by league"
    )
    audit_p.add_argument("--season", help="Filter by season (e.g. '2024-25', 'E2024')")
    audit_p.add_argument(
        "--detailed",
        action="store_true",
        help="Print all missing IDs in output",
    )
    audit_p.add_argument(
        "--json", action="store_true", help="Output audit report as JSON"
    )

    # list subcommand (list bronze keys)
    ls = sub.add_parser("list", help="List stored Bronze keys under a prefix")
    ls.add_argument("prefix", nargs="?", default="", help="S3 prefix (e.g. 'nba/')")

    # extractors subcommand (shortcut to list extractors)
    sub.add_parser("extractors", help="List all registered extractors")

    # config subcommand (manage config.json)
    config_p = sub.add_parser("config", help="View or save settings to config.json")
    config_p.add_argument(
        "--save",
        action="store_true",
        help="Save current active configuration to config.json",
    )
    config_p.add_argument(
        "--show", action="store_true", help="Display current configuration as JSON"
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    for noisy in ("botocore", "boto3", "urllib3", "s3transfer"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    if args.command == "extractors" or (args.command == "extract" and args.list):
        print("Available extractors:")
        for item in list_available_extractors():
            print(f"  - {item}")
        return 0

    if args.command == "config":
        import json

        settings = get_settings()
        if args.save:
            path = settings.save_to_json()
            print(f"Configuration successfully saved to: {path}")
        if args.show or not args.save:
            print(json.dumps(settings.model_dump(), indent=2))
        return 0

    if args.command == "list":
        storage = get_bronze_storage()
        keys = storage.list_keys(args.prefix)
        if not keys:
            print(f"No objects found under prefix: '{args.prefix}'")
        for key in keys:
            print(key)
        return 0

    if args.command == "extract":
        if not args.league or not args.endpoint:
            print(
                "Error: Both 'league' and 'endpoint' are required for extract. Run with --list to see options."
            )
            return 2
        if not args.season:
            print(
                "Error: --season is required (e.g. --season 2024-25 or --season E2024)."
            )
            return 2

        try:
            extractor_cls = get_extractor_class(args.league, args.endpoint)
        except ValueError as exc:
            print(f"Error: {exc}")
            return 2

        storage = get_bronze_storage()
        try:
            storage.ensure_bucket_exists()
        except Exception as exc:
            print(f"Error connecting to storage: {exc}")
            return 1

        extractor = extractor_cls(
            args.season,
            storage=storage,
            overwrite=args.overwrite,
            start=args.start,
            end=args.end,
            limit=args.limit,
        )

        summary = extractor.run()
        print(
            f"\nExtraction complete: {summary.fetched} fetched, {summary.skipped} skipped, {summary.failed} failed."
        )
        if summary.errors:
            print("\nErrors encountered:")
            for key, err in summary.errors:
                print(f"  - {key}: {err}")
            return 1
        return 0

    if args.command == "backfill":
        if args.season:
            seasons = [args.season]
        elif args.start_season and args.end_season:
            try:
                seasons = parse_season_range(
                    args.league, args.start_season, args.end_season
                )
            except ValueError as exc:
                print(f"Error parsing season range: {exc}")
                return 2
        else:
            print(
                "Error: Either --season or both --start-season and --end-season are required."
            )
            return 2

        include = [e.strip() for e in args.include.split(",")] if args.include else None
        exclude = [e.strip() for e in args.exclude.split(",")] if args.exclude else None
        try:
            endpoints = resolve_endpoints(args.league, include=include, exclude=exclude)
        except ValueError as exc:
            print(f"Error resolving endpoints: {exc}")
            return 2

        orchestrator = BackfillOrchestrator()
        summary = orchestrator.run(
            league=args.league,
            seasons=seasons,
            endpoints=endpoints,
            overwrite=args.overwrite,
            limit=args.limit,
            start_date=args.start,
            end_date=args.end,
        )
        return 1 if summary.total_failed > 0 else 0

    if args.command == "daily":
        runner = DailyRunner()
        summary = runner.run(
            league=args.league,
            target_date=args.date,
            days_back=args.days_back,
            season=args.season,
            refresh_rosters=args.refresh_rosters,
        )
        return 1 if summary.total_failed > 0 else 0

    if args.command == "audit":
        auditor = BronzeAuditor()
        report = auditor.run_audit(league=args.league, season=args.season)
        if args.json:
            print(report.to_json())
        else:
            print(report.format_text(detailed=args.detailed))
        return 0

    return 0
