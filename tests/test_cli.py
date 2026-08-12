"""End-to-end CLI tests using the offline fixture (no network calls)."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from lms.cli import build_parser, main

FIXTURE = Path(__file__).parent / "fixtures" / "overpass_sample.json"


class ParserTests(unittest.TestCase):
    def test_bbox_is_parsed(self):
        args = build_parser().parse_args(["scan", "--bbox", "1,2,3,4"])
        self.assertEqual(args.bbox, (1.0, 2.0, 3.0, 4.0))

    def test_bad_bbox_is_rejected(self):
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["scan", "--bbox", "1,2,3"])


class ScanCommandTests(unittest.TestCase):
    def test_scan_from_fixture_writes_csv_and_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "scan.csv"
            db = Path(tmp) / "market.sqlite3"
            code = main(
                [
                    "scan",
                    "--fixture",
                    str(FIXTURE),
                    "--out",
                    str(out),
                    "--sqlite",
                    "--db-path",
                    str(db),
                ]
            )
            self.assertEqual(code, 0)
            self.assertTrue(db.exists())
            with out.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 5)


class LeadsCommandTests(unittest.TestCase):
    def test_leads_reads_scan_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            scan_out = Path(tmp) / "scan.csv"
            leads_out = Path(tmp) / "leads.csv"
            self.assertEqual(
                main(["scan", "--fixture", str(FIXTURE), "--out", str(scan_out)]), 0
            )
            self.assertEqual(
                main(
                    [
                        "leads",
                        "--csv",
                        str(scan_out),
                        "--max-score",
                        "25",
                        "--out",
                        str(leads_out),
                    ]
                ),
                0,
            )
            with leads_out.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            names = [r["name"] for r in rows]
            self.assertIn("Merkez Eczanesi", names)
            self.assertNotIn("Örnek Fizyoterapi Merkezi", names)

    def test_missing_csv_returns_error_code(self):
        self.assertEqual(main(["leads", "--csv", "/nonexistent/none.csv"]), 1)


if __name__ == "__main__":
    unittest.main()
