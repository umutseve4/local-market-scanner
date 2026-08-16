"""CLI tests for the v0.3.0 commands: --version, --track, runs, validate,
export, load-pg."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import lms
from lms.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "overpass_sample.json"


def run_cli(argv: list[str]) -> tuple[int, str]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = main(argv)
    return code, buffer.getvalue()


class VersionFlagTests(unittest.TestCase):
    def test_version_flag_prints_package_version(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), self.assertRaises(SystemExit) as ctx:
            main(["--version"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn(lms.__version__, buffer.getvalue())


class TrackAndRunsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / "scan.csv"
        self.db = Path(self.tmp.name) / "market.sqlite3"

    def scan_tracked(self) -> tuple[int, str]:
        return run_cli(
            [
                "scan",
                "--fixture",
                str(FIXTURE),
                "--out",
                str(self.out),
                "--track",
                "--db-path",
                str(self.db),
            ]
        )

    def test_track_records_run_and_prints_summary(self) -> None:
        code, output = self.scan_tracked()
        self.assertEqual(code, 0)
        self.assertIn("run #1", output)
        self.assertIn("5 new", output)
        self.assertTrue(self.db.exists())

    def test_track_implies_sqlite(self) -> None:
        # no --sqlite flag passed, --track alone must create the DB
        code, _ = self.scan_tracked()
        self.assertEqual(code, 0)
        self.assertTrue(self.db.exists())

    def test_second_run_reports_unchanged(self) -> None:
        self.scan_tracked()
        code, output = self.scan_tracked()
        self.assertEqual(code, 0)
        self.assertIn("run #2", output)
        self.assertIn("0 new", output)
        self.assertIn("5 unchanged", output)

    def test_runs_command_lists_history(self) -> None:
        self.scan_tracked()
        self.scan_tracked()
        code, output = run_cli(["runs", "--db-path", str(self.db)])
        self.assertEqual(code, 0)
        lines = [line for line in output.splitlines() if line.strip()]
        # header + two runs, newest first
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[1].lstrip().startswith("2"))
        self.assertTrue(lines[2].lstrip().startswith("1"))

    def test_runs_changes_view(self) -> None:
        self.scan_tracked()
        code, output = run_cli(
            ["runs", "--db-path", str(self.db), "--changes", "1"]
        )
        self.assertEqual(code, 0)
        self.assertIn("5 change(s) in run #1", output)
        self.assertIn("new", output)

    def test_runs_on_missing_db_fails_cleanly(self) -> None:
        code, _ = run_cli(
            ["runs", "--db-path", str(Path(self.tmp.name) / "nope.sqlite3")]
        )
        self.assertEqual(code, 1)


class ValidateCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.csv = Path(self.tmp.name) / "scan.csv"
        run_cli(["scan", "--fixture", str(FIXTURE), "--out", str(self.csv)])

    def test_validate_passes_on_fixture_output(self) -> None:
        code, output = run_cli(["validate", "--csv", str(self.csv)])
        self.assertEqual(code, 0)
        self.assertIn("PASS", output)
        self.assertIn("5/5", output)

    def test_validate_fails_on_broken_data(self) -> None:
        broken = Path(self.tmp.name) / "broken.csv"
        text = self.csv.read_text(encoding="utf-8")
        broken.write_text(
            text.replace("+902245550011", "0224 555 00 11"), encoding="utf-8"
        )
        code, output = run_cli(["validate", "--csv", str(broken)])
        self.assertEqual(code, 1)
        self.assertIn("FAIL", output)
        self.assertIn("phone_format", output)

    def test_validate_writes_json_report(self) -> None:
        report_path = Path(self.tmp.name) / "report.json"
        code, _ = run_cli(
            ["validate", "--csv", str(self.csv), "--report", str(report_path)]
        )
        self.assertEqual(code, 0)
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["total_records"], 5)

    def test_validate_writes_markdown_report(self) -> None:
        report_path = Path(self.tmp.name) / "report.md"
        code, _ = run_cli(
            ["validate", "--csv", str(self.csv), "--report", str(report_path)]
        )
        self.assertEqual(code, 0)
        self.assertIn(
            "# Veri Sözleşmesi Raporu",
            report_path.read_text(encoding="utf-8"),
        )

    def test_validate_missing_file(self) -> None:
        code, _ = run_cli(
            ["validate", "--csv", str(Path(self.tmp.name) / "x.csv")]
        )
        self.assertEqual(code, 1)


class ExportCommandTests(unittest.TestCase):
    def test_export_writes_parquet(self) -> None:
        try:
            import pyarrow  # noqa: F401,PLC0415
        except ImportError:  # pragma: no cover - depends on environment
            self.skipTest("pyarrow not installed")
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "scan.csv"
            out_dir = Path(tmp) / "pq"
            run_cli(["scan", "--fixture", str(FIXTURE), "--out", str(csv_path)])
            code, output = run_cli(
                [
                    "export",
                    "--csv",
                    str(csv_path),
                    "--out-dir",
                    str(out_dir),
                    "--scan-date",
                    "2026-08-16",
                ]
            )
            self.assertEqual(code, 0)
            self.assertIn("5 rows", output)
            files = list(out_dir.glob("scan_date=2026-08-16/part-*.parquet"))
            self.assertEqual(len(files), 1)

    def test_export_missing_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _ = run_cli(
                ["export", "--csv", str(Path(tmp) / "x.csv"), "--out-dir", tmp]
            )
            self.assertEqual(code, 1)


class LoadPgCommandTests(unittest.TestCase):
    def test_empty_dsn_is_config_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "scan.csv"
            run_cli(["scan", "--fixture", str(FIXTURE), "--out", str(csv_path)])
            code, _ = run_cli(["load-pg", "--csv", str(csv_path), "--dsn", ""])
            self.assertEqual(code, 1)

    def test_missing_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _ = run_cli(
                ["load-pg", "--csv", str(Path(tmp) / "x.csv"), "--dsn", "x"]
            )
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
