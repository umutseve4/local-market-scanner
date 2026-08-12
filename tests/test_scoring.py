"""Tests for lead filtering and ranking."""

from __future__ import annotations

import unittest

from lms.models import Business
from lms.scoring import (
    contactable,
    qualified_leads,
    summarise,
    without_social,
    without_website,
)


def make(name: str, **kwargs) -> Business:
    base = {
        "source": "osm",
        "source_id": f"node/{name}",
        "name": name,
        "category": "clinic",
    }
    base.update(kwargs)
    return Business(**base)


class FilterTests(unittest.TestCase):
    def setUp(self):
        self.items = [
            make("A", phone="+902241111111"),
            make("B", website="https://b.com", phone="+902242222222"),
            make("C", social_url="https://instagram.com/c"),
            make("D"),
        ]

    def test_without_website(self):
        names = [b.name for b in without_website(self.items)]
        self.assertEqual(names, ["A", "C", "D"])

    def test_without_social(self):
        names = [b.name for b in without_social(self.items)]
        self.assertEqual(names, ["A", "B", "D"])

    def test_contactable_requires_phone_or_email(self):
        names = [b.name for b in contactable(self.items)]
        self.assertEqual(names, ["A", "B"])

    def test_contactable_accepts_email_only(self):
        items = [make("E", email="e@example.com")]
        self.assertEqual([b.name for b in contactable(items)], ["E"])


class QualifiedLeadTests(unittest.TestCase):
    def test_filters_by_score_and_contact(self):
        items = [
            make("Zeta", phone="+902241111111"),  # 15 -> qualifies
            make("Alfa", phone="+902242222222"),  # 15 -> qualifies
            make("Beta", website="https://b.com", phone="+90224333333"),  # 55 -> no
            make("Gama"),  # score 0 but no contact -> no
        ]
        leads = qualified_leads(items, max_score=25)
        self.assertEqual([b.name for b in leads], ["Alfa", "Zeta"])

    def test_allow_no_contact(self):
        items = [make("Gama")]
        self.assertEqual(len(qualified_leads(items, require_contact=False)), 1)

    def test_ordering_is_deterministic_by_score_then_name(self):
        items = [
            make("Yankee", phone="+902241111111"),  # 15
            make("Alfa", email="a@a.com"),  # 10
            make("Bravo", phone="+902243333333"),  # 15
        ]
        leads = qualified_leads(items, max_score=25)
        self.assertEqual([b.name for b in leads], ["Alfa", "Bravo", "Yankee"])

    def test_higher_max_score_widens_the_funnel(self):
        items = [make("Beta", website="https://b.com", phone="+902241111111")]
        self.assertEqual(qualified_leads(items, max_score=25), [])
        self.assertEqual(len(qualified_leads(items, max_score=60)), 1)


class SummariseTests(unittest.TestCase):
    def test_counts_add_up(self):
        items = [
            make("A", phone="+902241111111"),
            make("B", website="https://b.com"),
            make("C", social_url="https://instagram.com/c"),
        ]
        stats = summarise(items)
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["with_website"], 1)
        self.assertEqual(stats["without_website"], 2)
        self.assertEqual(stats["with_phone"], 1)
        self.assertEqual(stats["with_social"], 1)
        self.assertEqual(
            stats["high_priority"] + stats["medium_priority"] + stats["low_priority"],
            3,
        )

    def test_empty_input(self):
        self.assertEqual(summarise([])["total"], 0)


if __name__ == "__main__":
    unittest.main()
