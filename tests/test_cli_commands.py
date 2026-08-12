"""End-to-end tests for the CLI commands (no network access)."""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from lms import cli
from lms.config import Settings
from lms.errors import ConfigError, OverpassUnavailableError

FIXTURE = Path(__file__).parent / "fixtures" / "overpass_sample.json"


class TestScanAndLeads(unittest.TestCase):
    def test_scan_from_fixture_writes_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "scan.csv"
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(
                    ["scan", "--fixture", str(FIXTURE), "--out", str(out)]
                )
            self.assertEqual(code, cli.EXIT_OK)
            self.assertTrue(out.exists())
            self.assertGreater(len(out.read_text(encoding="utf-8").splitlines()), 1)

    def test_leads_reads_the_scan_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "scan.csv"
            with redirect_stdout(io.StringIO()):
                cli.main(
                    ["scan", "--fixture", str(FIXTURE), "--out", str(out)]
                )
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(["leads", "--csv", str(out)])
            self.assertEqual(code, cli.EXIT_OK)

    def test_leads_on_missing_csv_returns_failure(self):
        with redirect_stdout(io.StringIO()):
            code = cli.main(["leads", "--csv", "/nonexistent/nope.csv"])
        self.assertEqual(code, cli.EXIT_FAILURE)


class TestBriefCommand(unittest.TestCase):
    def _scan(self, tmp: str) -> Path:
        out = Path(tmp) / "scan.csv"
        with redirect_stdout(io.StringIO()):
            cli.main(["scan", "--fixture", str(FIXTURE), "--out", str(out)])
        return out

    def test_brief_writes_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = self._scan(tmp)
            brief_path = Path(tmp) / "nested" / "brief.md"
            with redirect_stdout(io.StringIO()):
                code = cli.main(
                    ["brief", "--csv", str(csv_path), "--out", str(brief_path)]
                )
            self.assertEqual(code, cli.EXIT_OK)
            text = brief_path.read_text(encoding="utf-8")
            self.assertIn("Saha Görüşme Brifingi", text)
            self.assertIn("Önerilen teklif", text)

    def test_brief_creates_missing_parent_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = self._scan(tmp)
            brief_path = Path(tmp) / "a" / "b" / "c.md"
            with redirect_stdout(io.StringIO()):
                cli.main(["brief", "--csv", str(csv_path), "--out", str(brief_path)])
            self.assertTrue(brief_path.exists())

    def test_brief_limit_is_applied(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = self._scan(tmp)
            brief_path = Path(tmp) / "brief.md"
            with redirect_stdout(io.StringIO()):
                cli.main(
                    [
                        "brief",
                        "--csv",
                        str(csv_path),
                        "--out",
                        str(brief_path),
                        "--limit",
                        "1",
                    ]
                )
            text = brief_path.read_text(encoding="utf-8")
            self.assertIn("### 1.", text)
            self.assertNotIn("### 2.", text)

    def test_brief_on_missing_csv_returns_failure(self):
        with redirect_stdout(io.StringIO()):
            code = cli.main(["brief", "--csv", "/nonexistent/nope.csv"])
        self.assertEqual(code, cli.EXIT_FAILURE)


class TestDoctorCommand(unittest.TestCase):
    def test_offline_doctor_succeeds_without_network(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main(["doctor", "--offline"])
        self.assertEqual(code, cli.EXIT_OK)
        output = buf.getvalue()
        self.assertIn("Overpass URL", output)
        self.assertIn("skipped", output)

    def test_doctor_reports_failure_when_no_endpoint_answers(self):
        original = cli.overpass.check_status
        cli.overpass.check_status = lambda **kw: [
            ("https://a.test", False, "ConnectionError: boom")
        ]
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(["doctor"])
            self.assertEqual(code, cli.EXIT_SOURCE_DOWN)
            self.assertIn("0/1", buf.getvalue())
        finally:
            cli.overpass.check_status = original

    def test_doctor_succeeds_when_one_endpoint_answers(self):
        original = cli.overpass.check_status
        cli.overpass.check_status = lambda **kw: [
            ("https://a.test", False, "HTTP 504"),
            ("https://b.test", True, "HTTP 200"),
        ]
        try:
            with redirect_stdout(io.StringIO()):
                code = cli.main(["doctor"])
            self.assertEqual(code, cli.EXIT_OK)
        finally:
            cli.overpass.check_status = original

    def test_doctor_never_prints_the_api_key(self):
        settings = Settings(google_places_api_key="secret-key-value")
        self.assertNotIn("secret-key-value", repr(settings))


class TestExitCodeMapping(unittest.TestCase):
    """main() must translate exception types into stable shell exit codes."""

    def _run_leads_with_failing_loader(self, exc: Exception) -> int:
        original = cli.load_csv

        def boom(_path):
            raise exc

        cli.load_csv = boom
        try:
            with tempfile.TemporaryDirectory() as tmp:
                csv_path = Path(tmp) / "any.csv"
                csv_path.write_text("source\n", encoding="utf-8")
                with redirect_stdout(io.StringIO()):
                    return cli.main(["leads", "--csv", str(csv_path)])
        finally:
            cli.load_csv = original

    def test_source_error_maps_to_exit_3(self):
        code = self._run_leads_with_failing_loader(
            OverpassUnavailableError("every mirror is down")
        )
        self.assertEqual(code, cli.EXIT_SOURCE_DOWN)

    def test_config_error_maps_to_exit_1(self):
        code = self._run_leads_with_failing_loader(ConfigError("bad setting"))
        self.assertEqual(code, cli.EXIT_FAILURE)

    def test_unexpected_error_maps_to_exit_2(self):
        code = self._run_leads_with_failing_loader(RuntimeError("unexpected"))
        self.assertEqual(code, cli.EXIT_UNEXPECTED)


class TestParser(unittest.TestCase):
    def test_all_subcommands_are_registered(self):
        parser = cli.build_parser()
        for command in ("scan", "leads", "brief", "doctor"):
            self.assertIsNotNone(parser.parse_args([command]))

    def test_brief_defaults(self):
        args = cli.build_parser().parse_args(["brief"])
        self.assertEqual(args.max_score, 25)
        self.assertEqual(args.limit, 25)


if __name__ == "__main__":
    unittest.main()
