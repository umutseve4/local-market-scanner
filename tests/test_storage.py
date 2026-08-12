"""Tests for CSV export and SQLite persistence."""

from __future__ import annotations

import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from lms.models import Business
from lms.storage import CSV_COLUMNS, upsert_sqlite, write_csv


def make(name: str, **kwargs) -> Business:
    base = {
        "source": "osm",
        "source_id": f"node/{name}",
        "name": name,
        "category": "clinic",
    }
    base.update(kwargs)
    return Business(**base)


class WriteCsvTests(unittest.TestCase):
    def test_writes_header_and_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "out.csv"
            count = write_csv([make("A", phone="+902241111111"), make("B")], path)
            self.assertEqual(count, 2)
            with path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(list(rows[0].keys()), list(CSV_COLUMNS))
            self.assertEqual(rows[0]["name"], "A")
            self.assertEqual(rows[0]["digital_maturity_score"], "15")
            self.assertEqual(rows[0]["lead_priority"], "high")

    def test_empty_input_writes_header_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.csv"
            self.assertEqual(write_csv([], path), 0)
            self.assertEqual(
                path.read_text(encoding="utf-8").strip(), ",".join(CSV_COLUMNS)
            )


class SqliteTests(unittest.TestCase):
    def test_insert_then_upsert_keeps_one_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "market.sqlite3"
            upsert_sqlite([make("A")], db)
            upsert_sqlite([make("A", website="https://a.com")], db)
            with sqlite3.connect(db) as conn:
                rows = conn.execute(
                    "SELECT name, website, digital_maturity_score FROM businesses"
                ).fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][1], "https://a.com")
            self.assertEqual(rows[0][2], 40)

    def test_index_and_schema_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "market.sqlite3"
            upsert_sqlite([make("A")], db)
            with sqlite3.connect(db) as conn:
                names = {
                    r[0]
                    for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type IN ('table','index')"
                    )
                }
            self.assertIn("businesses", names)
            self.assertIn("idx_businesses_priority", names)


if __name__ == "__main__":
    unittest.main()
