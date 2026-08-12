"""Tests for the outreach brief renderer."""

from __future__ import annotations

import unittest
from datetime import date

from lms.models import Business
from lms.outreach import (
    category_label,
    contact_line,
    missing_assets,
    opening_line,
    recommended_offer,
    render_brief,
    render_lead,
)


def make_business(**overrides) -> Business:
    base = {
        "source": "osm",
        "source_id": "node/1",
        "name": "Test Diş Kliniği",
        "category": "dentist",
        "lat": 40.2,
        "lon": 29.0,
        "district": "Nilüfer",
        "address": "Test Caddesi 1",
        "phone": "+902241234567",
    }
    base.update(overrides)
    return Business(**base)


class TestCategoryLabel(unittest.TestCase):
    def test_known_category_translated(self):
        self.assertEqual(category_label("dentist"), "diş kliniği")

    def test_unknown_category_passes_through(self):
        self.assertEqual(category_label("blood_donation"), "blood_donation")


class TestMissingAssets(unittest.TestCase):
    def test_lists_every_gap(self):
        gaps = missing_assets(make_business())
        self.assertIn("web sitesi", gaps)
        self.assertIn("sosyal medya bağlantısı", gaps)
        self.assertIn("e-posta adresi", gaps)
        self.assertIn("çalışma saatleri bilgisi", gaps)

    def test_fully_equipped_business_has_no_gaps(self):
        business = make_business(
            website="https://example.com",
            social_url="https://instagram.com/example",
            email="a@example.com",
            opening_hours="Mo-Fr 09:00-18:00",
        )
        self.assertEqual(missing_assets(business), [])


class TestRecommendedOffer(unittest.TestCase):
    def test_no_website_and_no_social_gets_combined_offer(self):
        offer = recommended_offer(make_business())
        self.assertIn("Tek sayfalık tanıtım sitesi", offer)
        self.assertIn("Google Haritalar", offer)

    def test_social_only_business_gets_website_offer(self):
        business = make_business(social_url="https://instagram.com/x")
        self.assertIn("randevu formu", recommended_offer(business))

    def test_website_only_business_gets_instagram_offer(self):
        business = make_business(website="https://example.com")
        self.assertIn("Instagram", recommended_offer(business))

    def test_missing_hours_only_gets_profile_offer(self):
        business = make_business(
            website="https://example.com", social_url="https://instagram.com/x"
        )
        self.assertIn("Google İşletme Profili", recommended_offer(business))

    def test_complete_business_gets_audit_offer(self):
        business = make_business(
            website="https://example.com",
            social_url="https://instagram.com/x",
            opening_hours="Mo-Fr 09:00-18:00",
        )
        self.assertIn("denetimi", recommended_offer(business))


class TestOpeningLine(unittest.TestCase):
    def test_mentions_the_business_name(self):
        self.assertIn("Test Diş Kliniği", opening_line(make_business()))

    def test_website_owner_gets_a_different_line(self):
        business = make_business(website="https://example.com")
        self.assertIn("çevrimiçi görünürlüğü", opening_line(business))


class TestContactLine(unittest.TestCase):
    def test_joins_available_channels(self):
        business = make_business(email="a@example.com")
        self.assertIn("|", contact_line(business))

    def test_reports_when_nothing_is_available(self):
        business = make_business(phone=None)
        self.assertEqual(contact_line(business), "iletişim bilgisi yok")


class TestRenderLead(unittest.TestCase):
    def test_contains_all_required_fields(self):
        block = render_lead(make_business(), 1)
        for token in ("Kategori", "İletişim", "Dijital olgunluk skoru", "Eksikler"):
            self.assertIn(token, block)

    def test_index_is_used_in_the_heading(self):
        self.assertTrue(render_lead(make_business(), 7).startswith("### 7."))

    def test_unknown_district_is_labelled(self):
        block = render_lead(make_business(district=None), 1)
        self.assertIn("bilinmiyor", block)


class TestRenderBrief(unittest.TestCase):
    def test_header_contains_date_and_count(self):
        text = render_brief([make_business()], today=date(2025, 3, 1))
        self.assertIn("2025-03-01", text)
        self.assertIn("Brifingdeki lead sayısı: 1", text)

    def test_limit_is_respected(self):
        businesses = [make_business(source_id=f"node/{i}") for i in range(10)]
        text = render_brief(businesses, limit=3)
        self.assertIn("Brifingdeki lead sayısı: 3", text)
        self.assertNotIn("### 4.", text)

    def test_empty_input_produces_a_clear_message(self):
        text = render_brief([])
        self.assertIn("lead bulunamadı", text)

    def test_odbl_attribution_is_present(self):
        self.assertIn("ODbL", render_brief([make_business()]))

    def test_output_ends_with_newline(self):
        self.assertTrue(render_brief([]).endswith("\n"))


if __name__ == "__main__":
    unittest.main()
