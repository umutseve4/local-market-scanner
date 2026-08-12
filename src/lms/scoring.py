"""Lead filtering and ranking on top of the digital maturity score."""

from __future__ import annotations

from collections.abc import Iterable

from .models import Business


def without_website(businesses: Iterable[Business]) -> list[Business]:
    """Facilities with no usable website — the strongest sales signal."""
    return [b for b in businesses if not b.has_website]


def without_social(businesses: Iterable[Business]) -> list[Business]:
    """Facilities with no linked social profile."""
    return [b for b in businesses if not b.has_social]


def contactable(businesses: Iterable[Business]) -> list[Business]:
    """Facilities we can actually reach (phone or e-mail present)."""
    return [b for b in businesses if b.has_phone or b.email]


def qualified_leads(
    businesses: Iterable[Business],
    max_score: int = 25,
    require_contact: bool = True,
) -> list[Business]:
    """Return leads at or below ``max_score``, sorted best-first.

    Best-first means: lowest digital maturity score, then alphabetical name so
    the ordering is deterministic and diffable between runs.
    """
    items = list(businesses)
    if require_contact:
        items = contactable(items)
    selected = [b for b in items if b.digital_maturity_score() <= max_score]
    return sorted(selected, key=lambda b: (b.digital_maturity_score(), b.name))


def summarise(businesses: Iterable[Business]) -> dict[str, int]:
    """Aggregate counts used by the CLI summary and by tests."""
    items = list(businesses)
    return {
        "total": len(items),
        "with_website": sum(1 for b in items if b.has_website),
        "without_website": sum(1 for b in items if not b.has_website),
        "with_phone": sum(1 for b in items if b.has_phone),
        "with_social": sum(1 for b in items if b.has_social),
        "high_priority": sum(1 for b in items if b.lead_priority() == "high"),
        "medium_priority": sum(1 for b in items if b.lead_priority() == "medium"),
        "low_priority": sum(1 for b in items if b.lead_priority() == "low"),
    }
