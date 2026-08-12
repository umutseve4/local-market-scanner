"""Command line interface for local-market-scanner.

Examples
--------
    python -m lms.cli doctor
    python -m lms.cli scan --out data/bursa_health.csv
    python -m lms.cli scan --fixture tests/fixtures/overpass_sample.json
    python -m lms.cli leads --csv data/bursa_health.csv --max-score 25
    python -m lms.cli brief --csv data/bursa_health.csv --out data/brief.md

Exit codes
----------
    0  success
    1  expected failure (no data, validation error, missing file)
    2  unexpected error (see the traceback in the log)
    3  data source unreachable (network, TLS, or every mirror down)
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path

from .config import BURSA_BBOX, Settings
from .errors import ConfigError, SourceError
from .models import Business, validate
from .outreach import render_brief
from .scoring import qualified_leads, summarise
from .sources import overpass
from .storage import upsert_sqlite, write_csv

logger = logging.getLogger("lms")

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_UNEXPECTED = 2
EXIT_SOURCE_DOWN = 3


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
            return EXIT_FAILURE

    if not businesses:
        logger.error("No businesses returned. Check the bbox or the Overpass status.")
        return EXIT_FAILURE

    rows = write_csv(businesses, Path(args.out))
    print(f"CSV written: {args.out} ({rows} rows)")

    if args.sqlite:
        db_path = Path(args.db_path or settings.db_path)
        upsert_sqlite(businesses, db_path)
        print(f"SQLite updated: {db_path}")

    _print_summary(businesses)
    return EXIT_OK


def load_csv(path: Path) -> list[Business]:
    """Load a scan CSV back into Business objects.

    Raises:
        FileNotFoundError: if the CSV does not exist.
        KeyError: if a required column is missing.
    """
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
    return businesses


def cmd_leads(args: argparse.Namespace) -> int:
    path = Path(args.csv)
    if not path.exists():
        logger.error("CSV not found: %s. Run 'scan' first.", path)
        return EXIT_FAILURE

    businesses = load_csv(path)

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
    return EXIT_OK


def cmd_brief(args: argparse.Namespace) -> int:
    """Render a Markdown outreach brief from a scan CSV."""
    path = Path(args.csv)
    if not path.exists():
        logger.error("CSV not found: %s. Run 'scan' first.", path)
        return EXIT_FAILURE

    businesses = load_csv(path)
    leads = qualified_leads(
        businesses,
        max_score=args.max_score,
        require_contact=not args.allow_no_contact,
    )
    markdown = render_brief(leads, limit=args.limit)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")
    print(f"Brief written: {out_path} ({min(len(leads), args.limit)} leads)")
    return EXIT_OK


def cmd_doctor(args: argparse.Namespace) -> int:
    """Diagnose the environment: config, dependencies and Overpass reachability."""
    print("--- lms doctor ---\n")
    print(f"Python          : {sys.version.split()[0]}")

    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        print(f"Settings        : INVALID -> {exc}")
        return EXIT_FAILURE

    print(f"Overpass URL    : {settings.overpass_url}")
    print(f"Mirrors         : {len(settings.endpoints)} endpoint(s)")
    print(f"Timeout         : {settings.request_timeout}s")
    print(f"Max retries     : {settings.max_retries}")
    print(f"CA bundle       : {settings.ca_bundle or 'system default'}")
    print(f"DB path         : {settings.db_path}")
    print(f"Places API key  : {'set' if settings.google_places_api_key else 'not set'}")

    if args.offline:
        print("\nNetwork checks skipped (--offline).")
        return EXIT_OK

    print("\nProbing Overpass endpoints...")
    results = overpass.check_status(settings=settings)
    healthy = 0
    for url, ok, detail in results:
        status = "OK  " if ok else "FAIL"
        print(f"  [{status}] {url} -> {detail}")
        healthy += int(ok)

    print(f"\n{healthy}/{len(results)} endpoint(s) reachable.")
    if healthy == 0:
        print(
            "\nNo endpoint answered. Common causes:\n"
            "  * no outbound internet access (corporate proxy, sandbox, firewall)\n"
            "  * TLS interception -> set REQUESTS_CA_BUNDLE to your CA file\n"
            "  * every public mirror is temporarily rate limited -> retry later"
        )
        return EXIT_SOURCE_DOWN
    return EXIT_OK


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

    brief = sub.add_parser(
        "brief", help="Render a Markdown outreach brief from a scan CSV."
    )
    brief.add_argument("--csv", default="data/bursa_health.csv")
    brief.add_argument("--out", default="data/outreach_brief.md")
    brief.add_argument("--max-score", type=int, default=25)
    brief.add_argument("--limit", type=int, default=25)
    brief.add_argument("--allow-no-contact", action="store_true")
    brief.set_defaults(func=cmd_brief)

    doctor = sub.add_parser(
        "doctor", help="Check configuration and Overpass reachability."
    )
    doctor.add_argument(
        "--offline", action="store_true", help="Skip all network probes."
    )
    doctor.set_defaults(func=cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    try:
        return int(args.func(args))
    except SourceError as exc:
        logger.error("Data source unavailable: %s", exc)
        logger.error("Run 'lms doctor' to diagnose the connection.")
        return EXIT_SOURCE_DOWN
    except ConfigError as exc:
        logger.error("Configuration error: %s", exc)
        return EXIT_FAILURE
    except FileNotFoundError as exc:
        logger.error("File not found: %s", exc)
        return EXIT_FAILURE
    except Exception as exc:  # noqa: BLE001 - top-level guard for CLI UX
        logger.exception("Command failed: %s", exc)
        return EXIT_UNEXPECTED


if __name__ == "__main__":
    sys.exit(main())
