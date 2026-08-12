"""Domain models, normalisation and validation for scanned businesses."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

_PHONE_CLEAN_RE = re.compile(r"[^\d+]")
_URL_SCHEME_RE = re.compile(r"^https?://", re.IGNORECASE)


@dataclass
class Business:
    """A single health-sector facility discovered in the target area."""

    source: str
    source_id: str
    name: str
    category: str
    lat: float | None = None
    lon: float | None = None
    address: str | None = None
    district: str | None = None
    phone: str | None = None
    website: str | None = None
    email: str | None = None
    opening_hours: str | None = None
    social_url: str | None = None
    raw_tags: dict[str, Any] = field(default_factory=dict)

    # ---- derived ------------------------------------------------------
    @property
    def has_website(self) -> bool:
        return bool(self.website)

    @property
    def has_phone(self) -> bool:
        return bool(self.phone)

    @property
    def has_social(self) -> bool:
        return bool(self.social_url)

    def digital_maturity_score(self) -> int:
        """Score 0-100. Lower score = weaker digital presence = better lead.

        Weights are intentionally simple and documented so the ranking is
        auditable rather than a black box.
        """
        score = 0
        if self.has_website:
            score += 40
        if self.has_social:
            score += 25
        if self.has_phone:
            score += 15
        if self.email:
            score += 10
        if self.opening_hours:
            score += 10
        return score

    def lead_priority(self) -> str:
        """Bucket the lead so outreach can be prioritised."""
        score = self.digital_maturity_score()
        if score <= 25:
            return "high"
        if score <= 55:
            return "medium"
        return "low"

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row.pop("raw_tags", None)
        row["digital_maturity_score"] = self.digital_maturity_score()
        row["lead_priority"] = self.lead_priority()
        row["has_website"] = self.has_website
        row["has_social"] = self.has_social
        return row


def normalise_phone(raw: str | None) -> str | None:
    """Normalise a Turkish phone number to +90XXXXXXXXXX when possible."""
    if not raw:
        return None
    first = re.split(r"[;,/]", raw)[0]
    cleaned = _PHONE_CLEAN_RE.sub("", first)
    if not cleaned:
        return None
    if cleaned.startswith("+90"):
        digits = cleaned[3:]
    elif cleaned.startswith("90") and len(cleaned) >= 12:
        digits = cleaned[2:]
    elif cleaned.startswith("0"):
        digits = cleaned[1:]
    else:
        digits = cleaned.lstrip("+")
    if len(digits) != 10 or not digits.isdigit():
        return None
    return f"+90{digits}"


def normalise_website(raw: str | None) -> str | None:
    """Return a usable http(s) URL, or None when the value is unusable."""
    if not raw:
        return None
    value = raw.strip().split(";")[0].strip()
    if not value or value.lower() in {"no", "none", "yok", "-"}:
        return None
    if not _URL_SCHEME_RE.match(value):
        value = f"https://{value}"
    host = value.split("//", 1)[-1]
    if "." not in host or host.startswith("."):
        return None
    return value


def validate(businesses: list[Business]) -> list[str]:
    """Return human-readable data-quality problems; empty list means OK."""
    problems: list[str] = []
    seen: set[tuple[str, str]] = set()
    for item in businesses:
        key = (item.source, item.source_id)
        if key in seen:
            problems.append(f"duplicate source_id: {item.source}:{item.source_id}")
        seen.add(key)
        if not item.name or not item.name.strip():
            problems.append(f"missing name for {item.source}:{item.source_id}")
        if item.lat is not None and not (-90 <= item.lat <= 90):
            problems.append(f"latitude out of range for {item.source_id}: {item.lat}")
        if item.lon is not None and not (-180 <= item.lon <= 180):
            problems.append(f"longitude out of range for {item.source_id}: {item.lon}")
    return problems
