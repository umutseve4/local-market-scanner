"""Command line interface for local-market-scanner.

Examples
--------
    python -m lms.cli scan --out data/bursa_health.csv
    python -m lms.cli scan --fixture tests/fixtures/overpass_sample.json
    python -m lms.cli leads --csv data/bursa_health.csv --max-score 25
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path

from .config import BURSA_BBOX, Settings
from .models import Business, validate
from .scoring import qualified_leads, summarise
from .sources import overpass
from .storage import upsert_sqlite, write_csv

logger = logging.getLogger("lms")


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )


def _parse_bbox(value: str) -> tuple[float, float, float, float]:
    parts = [float(p) for p in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bbox must be 'south,west,north,east'")
    return (parts[0], parts[1], parts[2], parts[3])


def _print_summary(businesses: list[Business]) -> None:
    stats = summarise(businesses)
    width = max(len(k) for k in stats)
    print("\n--- summary ---")
    for key, value in stats.items():
        print(f"{key.ljust(width)} : {value}")


def cmd_scan(args: argparse.Namespace) -> int:
    settings = Settings.from_env()

    if args.fixture:
        payload = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
        businesses = overpass.parse_response(payload)
        logger.info("Loaded %d businesses from fixture", len(businesses))
    else:
        businesses = overpass.fetch(args.bbox, settings=settings)

    problems = validate(businesses)
    if problems:
        logger.warning("%d data-quality problems detected", len(problems))
        for problem in problems[:10]:
            logger.warning("  %s", problem)
        if args.strict:
            logger.error("Aborting because --strict was set.")
            return 1

    if not businesses:
        logger.error("No businesses returned. Check the bbox or the Overpass status.")
        return 1

    rows = write_csv(businesses, Path(args.out))
    print(f"CSV written: {args.out} ({rows} rows)")

    if args.sqlite:
        db_path = Path(args.db_path or settings.db_path)
        upsert_sqlite(businesses, db_path)
        print(f"SQLite updated: {db_path}")

    _print_summary(businesses)
    return 0


def cmd_leads(args: argparse.Namespace) -> int:
    path = Path(args.csv)
    if not path.exists():
        logger.error("CSV not found: %s. Run 'scan' first.", path)
        return 1

    businesses: list[Business] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            businesses.append(
                Business(
                    source=row["source"],
                    source_id=row["source_id"],
                    name=row["name"],
                    category=row["category"],
                    district=row.get("district") or None,
                    address=row.get("address") or None,
                    phone=row.get("phone") or None,
                    email=row.get("email") or None,
                    website=row.get("website") or None,
                    social_url=row.get("social_url") or None,
                    opening_hours=row.get("opening_hours") or None,
                )
            )

    leads = qualified_leads(
        businesses,
        max_score=args.max_score,
        require_contact=not args.allow_no_contact,
    )
    print(f"{len(leads)} qualified leads (max_score={args.max_score})\n")
    for lead in leads[: args.limit]:
        print(
            f"[{lead.digital_maturity_score():>3}] {lead.name} "
            f"| {lead.category} | {lead.phone or lead.email or '-'} "
            f"| {lead.district or '-'}"
        )

    if args.out:
        rows = write_csv(leads, Path(args.out))
        print(f"\nLeads CSV written: {args.out} ({rows} rows)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lms", description="Local market scanner for health-sector leads."
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="Fetch facilities and export them.")
    scan.add_argument("--bbox", type=_parse_bbox, default=BURSA_BBOX)
    scan.add_argument("--out", default="data/bursa_health.csv")
    scan.add_argument("--fixture", help="Parse a saved Overpass JSON instead of HTTP.")
    scan.add_argument("--sqlite", action="store_true", help="Also upsert into SQLite.")
    scan.add_argument("--db-path", help="Override the SQLite path.")
    scan.add_argument("--strict", action="store_true", help="Fail on validation errors.")
    scan.set_defaults(func=cmd_scan)

    leads = sub.add_parser("leads", help="Rank qualified leads from a scan CSV.")
    leads.add_argument("--csv", default="data/bursa_health.csv")
    leads.add_argument("--max-score", type=int, default=25)
    leads.add_argument("--limit", type=int, default=50)
    leads.add_argument("--allow-no-contact", action="store_true")
    leads.add_argument("--out", help="Optional CSV path for the lead list.")
    leads.set_defaults(func=cmd_leads)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    try:
        return int(args.func(args))
    except Exception as exc:  # noqa: BLE001 - top-level guard for CLI UX
        logger.exception("Command failed: %s", exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
