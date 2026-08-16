"""Tests for the scan-run history module."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from lms.history import (
    changes_for_run,
    init_history,
    list_runs,
    record_scan_run,
)
from lms.models import Business


def make_business(**overrides: object) -> Business:
    defaults: dict = {
        "source": "overpass",
        "source_id": "node/1",
        "name": "Test Eczanesi",
        "category": "pharmacy",
        "phone": "+905551112233",
    }
    defaults.update(overrides)
    return Business(**defaults)


class HistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "test.db"

    def test_init_history_creates_tables(self) -> None:
        init_history(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        self.assertIn("scan_runs", tables)
        self.assertIn("business_history", tables)
        self.assertIn("businesses", tables)

    def test_first_run_marks_everything_new(self) -> None:
        result = record_scan_run([make_business()], self.db)
        self.assertEqual(result.total, 1)
        self.assertEqual(result.new, 1)
        self.assertEqual(result.changed, 0)
        self.assertEqual(result.unchanged, 0)

    def test_identical_rerun_is_unchanged(self) -> None:
        record_scan_run([make_business()], self.db)
        result = record_scan_run([make_business()], self.db)
        self.assertEqual(result.new, 0)
        self.assertEqual(result.changed, 0)
        self.assertEqual(result.unchanged, 1)

    def test_modified_record_is_changed(self) -> None:
        record_scan_run([make_business()], self.db)
        result = record_scan_run(
            [make_business(website="https://example.com")], self.db
        )
        self.assertEqual(result.changed, 1)
        self.assertEqual(result.new, 0)

    def test_current_state_table_still_upserted(self) -> None:
        record_scan_run([make_business()], self.db)
        record_scan_run([make_business(website="https://example.com")], self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            rows = conn.execute(
                "SELECT website, COUNT(*) FROM businesses "
                "GROUP BY source, source_id"
            ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "https://example.com")
        self.assertEqual(rows[0][1], 1)

    def test_list_runs_newest_first(self) -> None:
        record_scan_run([make_business()], self.db)
        record_scan_run([make_business()], self.db)
        runs = list_runs(self.db)
        self.assertEqual(len(runs), 2)
        self.assertGreater(runs[0]["run_id"], runs[1]["run_id"])
        self.assertEqual(runs[0]["total_count"], 1)
        self.assertIsNotNone(runs[0]["finished_at"])

    def test_changes_for_run_excludes_unchanged(self) -> None:
        first = record_scan_run([make_business()], self.db)
        second = record_scan_run([make_business()], self.db)
        self.assertEqual(len(changes_for_run(self.db, first.run_id)), 1)
        self.assertEqual(len(changes_for_run(self.db, second.run_id)), 0)

    def test_changes_snapshot_is_decoded_json(self) -> None:
        result = record_scan_run([make_business()], self.db)
        changes = changes_for_run(self.db, result.run_id)
        self.assertEqual(changes[0]["change_type"], "new")
        self.assertEqual(changes[0]["snapshot"]["name"], "Test Eczanesi")

    def test_multiple_businesses_counted(self) -> None:
        batch = [
            make_business(),
            make_business(source_id="node/2", name="B Kliniği"),
        ]
        record_scan_run(batch, self.db)
        result = record_scan_run(
            [
                make_business(website="https://a.com"),
                make_business(source_id="node/2", name="B Kliniği"),
                make_business(source_id="node/3", name="C Merkezi"),
            ],
            self.db,
        )
        self.assertEqual(result.total, 3)
        self.assertEqual(result.new, 1)
        self.assertEqual(result.changed, 1)
        self.assertEqual(result.unchanged, 1)


if __name__ == "__main__":
    unittest.main()
