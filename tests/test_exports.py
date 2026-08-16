"""Tests for the Parquet export module (requires pyarrow)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lms.exports import export_parquet, partition_dir
from lms.models import Business
from lms.storage import CSV_COLUMNS

try:
    import pyarrow.parquet as pq

    HAS_PYARROW = True
except ImportError:  # pragma: no cover - depends on environment
    HAS_PYARROW = False


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


class PartitionDirTests(unittest.TestCase):
    def test_hive_style_layout(self) -> None:
        result = partition_dir(Path("/data/pq"), "2026-08-16")
        self.assertEqual(result, Path("/data/pq/scan_date=2026-08-16"))


@unittest.skipUnless(HAS_PYARROW, "pyarrow not installed")
class ExportParquetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)

    def test_writes_partitioned_file(self) -> None:
        target, rows = export_parquet(
            [make_business()], self.out, scan_date="2026-08-16"
        )
        self.assertEqual(rows, 1)
        self.assertTrue(target.exists())
        self.assertEqual(target.parent.name, "scan_date=2026-08-16")
        self.assertEqual(target.name, "part-0000.parquet")

    def test_schema_matches_csv_columns(self) -> None:
        target, _ = export_parquet(
            [make_business()], self.out, scan_date="2026-08-16"
        )
        table = pq.read_table(target)
        self.assertEqual(tuple(table.column_names), tuple(CSV_COLUMNS))

    def test_values_round_trip(self) -> None:
        target, _ = export_parquet(
            [make_business(website="https://example.com")],
            self.out,
            scan_date="2026-08-16",
        )
        data = pq.read_table(target).to_pylist()
        self.assertEqual(data[0]["name"], "Test Eczanesi")
        self.assertEqual(data[0]["website"], "https://example.com")
        self.assertEqual(data[0]["digital_maturity_score"], 55)

    def test_empty_batch_raises(self) -> None:
        with self.assertRaises(ValueError):
            export_parquet([], self.out, scan_date="2026-08-16")

    def test_default_date_is_used(self) -> None:
        target, _ = export_parquet([make_business()], self.out)
        self.assertTrue(target.parent.name.startswith("scan_date="))


if __name__ == "__main__":
    unittest.main()
