"""Tests for the Overpass source. No network access: a JSON fixture is used."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from lms.config import BURSA_BBOX
from lms.sources.overpass import build_query, parse_element, parse_response

FIXTURE = Path(__file__).parent / "fixtures" / "overpass_sample.json"


class BuildQueryTests(unittest.TestCase):
    def test_contains_output_directives(self):
        query = build_query(BURSA_BBOX)
        self.assertIn("[out:json]", query)
        self.assertIn("out center tags;", query)

    def test_contains_bbox_values(self):
        query = build_query((1.0, 2.0, 3.0, 4.0))
        self.assertIn("(1.0,2.0,3.0,4.0)", query)

    def test_queries_both_nodes_and_ways(self):
        query = build_query(BURSA_BBOX)
        self.assertIn("node[", query)
        self.assertIn("way[", query)

    def test_custom_filters_are_used(self):
        query = build_query((1.0, 2.0, 3.0, 4.0), filters={"amenity": ("dentist",)})
        self.assertIn('["amenity"~"^(dentist)$"]', query)
        self.assertNotIn("healthcare", query)


class ParseElementTests(unittest.TestCase):
    def test_skips_unnamed_elements(self):
        self.assertIsNone(parse_element({"type": "node", "id": 1, "tags": {"amenity": "clinic"}}))

    def test_skips_elements_without_tags(self):
        self.assertIsNone(parse_element({"type": "node", "id": 1}))

    def test_way_uses_center_coordinates(self):
        business = parse_element(
            {
                "type": "way",
                "id": 7,
                "center": {"lat": 40.1, "lon": 29.1},
                "tags": {"name": "X", "amenity": "hospital"},
            }
        )
        self.assertEqual(business.source_id, "way/7")
        self.assertEqual(business.lat, 40.1)
        self.assertEqual(business.lon, 29.1)

    def test_normalises_phone_and_website(self):
        business = parse_element(
            {
                "type": "node",
                "id": 8,
                "lat": 40.0,
                "lon": 29.0,
                "tags": {
                    "name": "Y",
                    "amenity": "dentist",
                    "phone": "0224 123 45 67",
                    "website": "www.y.com",
                },
            }
        )
        self.assertEqual(business.phone, "+902241234567")
        self.assertEqual(business.website, "https://www.y.com")


class ParseResponseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.businesses = parse_response(cls.payload)

    def test_unnamed_element_is_dropped(self):
        # The fixture has 6 elements, one of which has no name.
        self.assertEqual(len(self.payload["elements"]), 6)
        self.assertEqual(len(self.businesses), 5)

    def test_placeholder_website_is_rejected(self):
        pharmacy = next(b for b in self.businesses if b.name == "Merkez Eczanesi")
        self.assertIsNone(pharmacy.website)
        self.assertEqual(pharmacy.lead_priority(), "high")

    def test_social_tag_is_detected(self):
        optician = next(b for b in self.businesses if b.name == "Görme Optik")
        self.assertEqual(optician.social_url, "https://facebook.com/gormeoptik")

    def test_fully_digital_business_scores_high(self):
        physio = next(b for b in self.businesses if "Fizyoterapi" in b.name)
        self.assertEqual(physio.digital_maturity_score(), 100)
        self.assertEqual(physio.lead_priority(), "low")

    def test_address_is_composed(self):
        dentist = next(b for b in self.businesses if "Diş" in b.name)
        self.assertEqual(dentist.address, "Ihsaniye Caddesi 12 Bursa")

    def test_category_prefers_healthcare_tag(self):
        dentist = next(b for b in self.businesses if "Diş" in b.name)
        self.assertEqual(dentist.category, "dentist")


if __name__ == "__main__":
    unittest.main()
