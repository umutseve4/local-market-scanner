"""Tests for the PostgreSQL loader (pure SQL-building parts, no server)."""

from __future__ import annotations

import unittest

from lms.errors import ConfigError
from lms.models import Business
from lms.pg_loader import (
    build_insert_statement,
    load_postgres,
    rows_from_businesses,
)
from lms.storage import CSV_COLUMNS


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


class BuildInsertStatementTests(unittest.TestCase):
    def test_targets_businesses_table(self) -> None:
        statement = build_insert_statement()
        self.assertTrue(statement.startswith("INSERT INTO businesses ("))

    def test_contains_all_csv_columns(self) -> None:
        statement = build_insert_statement()
        for column in CSV_COLUMNS:
            self.assertIn(column, statement)
            self.assertIn(f"%({column})s", statement)

    def test_upsert_on_natural_key(self) -> None:
        statement = build_insert_statement()
        self.assertIn("ON CONFLICT (source, source_id) DO UPDATE SET", statement)
        self.assertNotIn("source = EXCLUDED.source", statement)
        self.assertNotIn("source_id = EXCLUDED.source_id", statement)
        self.assertIn("name = EXCLUDED.name", statement)
        self.assertIn("scanned_at = now()", statement)


class RowsFromBusinessesTests(unittest.TestCase):
    def test_row_keys_match_columns(self) -> None:
        rows = rows_from_businesses([make_business()])
        self.assertEqual(len(rows), 1)
        self.assertEqual(set(rows[0].keys()), set(CSV_COLUMNS))

    def test_flags_are_booleans(self) -> None:
        rows = rows_from_businesses(
            [make_business(website="https://example.com")]
        )
        self.assertIs(rows[0]["has_website"], True)
        self.assertIs(rows[0]["has_social"], False)

    def test_score_and_priority_computed(self) -> None:
        rows = rows_from_businesses([make_business()])
        self.assertEqual(rows[0]["digital_maturity_score"], 15)
        self.assertEqual(rows[0]["lead_priority"], "high")


class LoadPostgresGuardTests(unittest.TestCase):
    def test_empty_dsn_raises_config_error(self) -> None:
        with self.assertRaises(ConfigError):
            load_postgres([make_business()], "")

    def test_whitespace_dsn_raises_config_error(self) -> None:
        with self.assertRaises(ConfigError):
            load_postgres([make_business()], "   ")


if __name__ == "__main__":
    unittest.main()
