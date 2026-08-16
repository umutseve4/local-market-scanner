"""Data contract: the formal quality gate for scanned businesses.

``models.validate`` gives quick human-readable warnings. This module turns
those informal checks into an explicit *contract*: a fixed set of named rules,
a machine-readable report (JSON) and a human report (Markdown), plus a hard
pass/fail verdict the CLI can map to an exit code.

Rules
-----
required        source, source_id, name, category must be non-empty
unique_key      (source, source_id) must be unique in the batch
score_range     digital_maturity_score must be 0..100
priority_enum   lead_priority must be high / medium / low
lat_range       lat is NULL or -90..90
lon_range       lon is NULL or -180..180
website_scheme  website is NULL or starts with http:// or https://
phone_format    phone is NULL or +90 followed by 10 digits
email_format    email is NULL or contains exactly one '@' with a dot after it
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .models import Business

_PHONE_RE = re.compile(r"^\+90\d{10}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)

VALID_PRIORITIES = frozenset({"high", "medium", "low"})


@dataclass(frozen=True)
class Violation:
    """One broken rule on one record."""

    rule: str
    key: str
    detail: str


@dataclass
class ContractReport:
    """Outcome of running the full contract over a batch."""

    total: int
    violations: list[Violation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations

    @property
    def failed_keys(self) -> set[str]:
        return {v.key for v in self.violations}

    def summary(self) -> dict[str, Any]:
        by_rule = Counter(v.rule for v in self.violations)
        return {
            "total_records": self.total,
            "passed_records": self.total - len(self.failed_keys),
            "failed_records": len(self.failed_keys),
            "violations": len(self.violations),
            "by_rule": dict(sorted(by_rule.items())),
            "ok": self.ok,
        }

    def to_json(self) -> str:
        payload = self.summary()
        payload["details"] = [
            {"rule": v.rule, "key": v.key, "detail": v.detail}
            for v in self.violations
        ]
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        lines = [
            "# Veri Sözleşmesi Raporu",
            "",
            f"- Toplam kayıt : {self.total}",
            f"- Geçen kayıt  : {self.total - len(self.failed_keys)}",
            f"- Kalan kayıt  : {len(self.failed_keys)}",
            f"- Sonuç        : {'PASS' if self.ok else 'FAIL'}",
            "",
        ]
        if self.violations:
            lines += ["| Kural | Kayıt | Detay |", "| --- | --- | --- |"]
            lines += [
                f"| {v.rule} | {v.key} | {v.detail} |" for v in self.violations
            ]
            lines.append("")
        return "\n".join(lines)


def _key(item: Business) -> str:
    return f"{item.source}:{item.source_id}"


def check_contract(businesses: list[Business]) -> ContractReport:
    """Run every contract rule and return the full report."""
    report = ContractReport(total=len(businesses))
    seen: set[tuple[str, str]] = set()

    for item in businesses:
        key = _key(item)

        for column in ("source", "source_id", "name", "category"):
            value = getattr(item, column)
            if not value or not str(value).strip():
                report.violations.append(
                    Violation("required", key, f"{column} is empty")
                )

        pair = (item.source, item.source_id)
        if pair in seen:
            report.violations.append(
                Violation("unique_key", key, "duplicate (source, source_id)")
            )
        seen.add(pair)

        score = item.digital_maturity_score()
        if not 0 <= score <= 100:
            report.violations.append(
                Violation("score_range", key, f"score {score} outside 0..100")
            )

        priority = item.lead_priority()
        if priority not in VALID_PRIORITIES:
            report.violations.append(
                Violation("priority_enum", key, f"unknown priority {priority!r}")
            )

        if item.lat is not None and not -90 <= item.lat <= 90:
            report.violations.append(
                Violation("lat_range", key, f"lat {item.lat} outside -90..90")
            )
        if item.lon is not None and not -180 <= item.lon <= 180:
            report.violations.append(
                Violation("lon_range", key, f"lon {item.lon} outside -180..180")
            )

        if item.website is not None and not _URL_RE.match(item.website):
            report.violations.append(
                Violation("website_scheme", key, f"no http(s) scheme: {item.website}")
            )
        if item.phone is not None and not _PHONE_RE.match(item.phone):
            report.violations.append(
                Violation("phone_format", key, f"not +90XXXXXXXXXX: {item.phone}")
            )
        if item.email is not None and not _EMAIL_RE.match(item.email):
            report.violations.append(
                Violation("email_format", key, f"not a usable email: {item.email}")
            )

    return report
