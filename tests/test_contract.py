"""Tests for the data contract / quality gate."""

from __future__ import annotations

import json
import unittest

from lms.contract import check_contract
from lms.models import Business


def make_business(**overrides: object) -> Business:
    defaults: dict = {
        "source": "overpass",
        "source_id": "node/1",
        "name": "Test Eczanesi",
        "category": "pharmacy",
        "phone": "+905551112233",
        "lat": 40.19,
        "lon": 29.06,
    }
    defaults.update(overrides)
    return Business(**defaults)


class ContractTests(unittest.TestCase):
    def test_clean_batch_passes(self) -> None:
        report = check_contract([make_business()])
        self.assertTrue(report.ok)
        self.assertEqual(report.summary()["failed_records"], 0)

    def test_empty_name_fails_required(self) -> None:
        report = check_contract([make_business(name="  ")])
        self.assertFalse(report.ok)
        self.assertIn("required", {v.rule for v in report.violations})

    def test_duplicate_key_detected(self) -> None:
        report = check_contract([make_business(), make_business()])
        self.assertIn("unique_key", {v.rule for v in report.violations})

    def test_lat_lon_out_of_range(self) -> None:
        report = check_contract([make_business(lat=91.0, lon=-181.0)])
        rules = {v.rule for v in report.violations}
        self.assertIn("lat_range", rules)
        self.assertIn("lon_range", rules)

    def test_website_without_scheme_fails(self) -> None:
        report = check_contract([make_business(website="example.com")])
        self.assertIn("website_scheme", {v.rule for v in report.violations})

    def test_website_with_scheme_passes(self) -> None:
        report = check_contract([make_business(website="https://example.com")])
        self.assertTrue(report.ok)

    def test_bad_phone_fails(self) -> None:
        report = check_contract([make_business(phone="0555 111 22 33")])
        self.assertIn("phone_format", {v.rule for v in report.violations})

    def test_bad_email_fails(self) -> None:
        report = check_contract([make_business(email="not-an-email")])
        self.assertIn("email_format", {v.rule for v in report.violations})

    def test_good_email_passes(self) -> None:
        report = check_contract([make_business(email="info@klinik.com.tr")])
        self.assertTrue(report.ok)

    def test_none_optionals_do_not_fail(self) -> None:
        report = check_contract(
            [make_business(phone=None, website=None, email=None, lat=None, lon=None)]
        )
        self.assertTrue(report.ok)

    def test_summary_counts(self) -> None:
        report = check_contract(
            [make_business(), make_business(source_id="node/2", name="")]
        )
        summary = report.summary()
        self.assertEqual(summary["total_records"], 2)
        self.assertEqual(summary["failed_records"], 1)
        self.assertEqual(summary["passed_records"], 1)
        self.assertFalse(summary["ok"])

    def test_to_json_is_valid_json(self) -> None:
        report = check_contract([make_business(email="broken")])
        payload = json.loads(report.to_json())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["details"][0]["rule"], "email_format")

    def test_to_markdown_contains_verdict(self) -> None:
        ok_report = check_contract([make_business()])
        self.assertIn("PASS", ok_report.to_markdown())
        bad_report = check_contract([make_business(name="")])
        markdown = bad_report.to_markdown()
        self.assertIn("FAIL", markdown)
        self.assertIn("| required |", markdown)


if __name__ == "__main__":
    unittest.main()
