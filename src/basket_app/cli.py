"""Command-line entry point.

python -m basket_app extract nba schedule --season 2025-26
python -m basket_app extract euroleague games --season E2025 --overwrite
python -m basket_app list nba/
"""

import argparse
import logging
from datetime import date

from basket_app.core.logging import setup_logging
from basket_app.core.storage import get_bronze_storage
from basket_app.extract.registry import EXTRACTORS, get_extractor_class


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="basket_app")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    extract = sub.add_parser("extract", help="Fetch raw data into the bronze bucket")
    extract.add_argument("league", choices=sorted({l for l, _ in EXTRACTORS}))
    extract.add_argument(
        "endpoint", help="e.g. " + ", ".join(sorted({e for _, e in EXTRACTORS}))
    )
    extract.add_argument(
        "--season",
        required=True,
        help="NBA: '2025-26'. EuroLeague: season code such as 'E2025'.",
    )
    extract.add_argument(
        "--start",
        type=date.fromisoformat,
        help="YYYY-MM-DD (date-partitioned endpoints)",
    )
    extract.add_argument("--end", type=date.fromisoformat, help="YYYY-MM-DD inclusive")
    extract.add_argument(
        "--overwrite", action="store_true", help="Re-fetch objects that already exist"
    )

    ls = sub.add_parser("list", help="List bronze keys under a prefix")
    ls.add_argument("prefix", nargs="?", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(logging.DEBUG if args.verbose else logging.INFO)
    storage = get_bronze_storage()

    if args.command == "list":
        for key in storage.iter_keys(args.prefix):
            print(key)
        return 0

    storage.ensure_bucket_exists()
    extractor_cls = get_extractor_class(args.league, args.endpoint)
    extractor = extractor_cls(
        args.season,
        storage=storage,
        overwrite=args.overwrite,
        start=args.start,
        end=args.end,
    )
    summary = extractor.run()
    for key, err in summary.errors:
        print(f"FAILED {key}: {err}")
    return 1 if summary.failed else 0
