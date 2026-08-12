"""Tests for normalisation, scoring and validation."""

from __future__ import annotations

import unittest

from lms.models import Business, normalise_phone, normalise_website, validate


def make(**kwargs) -> Business:
    base = {
        "source": "osm",
        "source_id": "node/1",
        "name": "Test Klinik",
        "category": "clinic",
    }
    base.update(kwargs)
    return Business(**base)


class NormalisePhoneTests(unittest.TestCase):
    def test_local_format(self):
        self.assertEqual(normalise_phone("0224 123 45 67"), "+902241234567")

    def test_international_format(self):
        self.assertEqual(normalise_phone("+90 224 987 65 43"), "+902249876543")

    def test_country_code_without_plus(self):
        self.assertEqual(normalise_phone("902241112233"), "+902241112233")

    def test_takes_first_of_multiple(self):
        self.assertEqual(normalise_phone("0224 111 22 33; 0224 444 55 66"), "+902241112233")

    def test_rejects_too_short(self):
        self.assertIsNone(normalise_phone("123"))

    def test_handles_none_and_empty(self):
        self.assertIsNone(normalise_phone(None))
        self.assertIsNone(normalise_phone(""))


class NormaliseWebsiteTests(unittest.TestCase):
    def test_adds_scheme(self):
        self.assertEqual(normalise_website("www.ornek.com"), "https://www.ornek.com")

    def test_keeps_existing_scheme(self):
        self.assertEqual(normalise_website("http://ornek.com"), "http://ornek.com")

    def test_rejects_placeholder_values(self):
        for value in ("yok", "none", "-", "  "):
            self.assertIsNone(normalise_website(value), value)

    def test_rejects_value_without_dot(self):
        self.assertIsNone(normalise_website("localhost"))


class ScoringTests(unittest.TestCase):
    def test_empty_business_scores_zero(self):
        self.assertEqual(make().digital_maturity_score(), 0)

    def test_website_dominates_score(self):
        self.assertEqual(make(website="https://a.com").digital_maturity_score(), 40)

    def test_full_profile_scores_100(self):
        business = make(
            website="https://a.com",
            social_url="https://instagram.com/a",
            phone="+902241234567",
            email="a@a.com",
            opening_hours="Mo-Fr 09:00-18:00",
        )
        self.assertEqual(business.digital_maturity_score(), 100)

    def test_priority_buckets(self):
        self.assertEqual(make(phone="+902241234567").lead_priority(), "high")
        self.assertEqual(
            make(website="https://a.com", phone="+902241234567").lead_priority(),
            "medium",
        )
        self.assertEqual(
            make(
                website="https://a.com",
                social_url="https://instagram.com/a",
                phone="+902241234567",
            ).lead_priority(),
            "low",
        )

    def test_to_row_contains_derived_fields(self):
        row = make(phone="+902241234567").to_row()
        self.assertIn("digital_maturity_score", row)
        self.assertIn("lead_priority", row)
        self.assertNotIn("raw_tags", row)
        self.assertFalse(row["has_website"])


class ValidateTests(unittest.TestCase):
    def test_clean_dataset_has_no_problems(self):
        self.assertEqual(validate([make(), make(source_id="node/2")]), [])

    def test_detects_duplicates(self):
        problems = validate([make(), make()])
        self.assertTrue(any("duplicate" in p for p in problems))

    def test_detects_bad_coordinates(self):
        problems = validate([make(lat=999.0)])
        self.assertTrue(any("latitude" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
