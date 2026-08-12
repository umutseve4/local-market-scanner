"""Configuration loading for local-market-scanner.

Secrets are read from environment variables only. Never hardcode keys.
See .env.example for the expected variable names.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Bounding box for Bursa province (south, west, north, east) in WGS84.
# Approximate provincial extent; override with --bbox if needed.
BURSA_BBOX = (39.85, 28.05, 40.55, 30.05)

# OpenStreetMap tags that identify health-sector facilities.
HEALTH_FILTERS: dict[str, tuple[str, ...]] = {
    "amenity": ("clinic", "doctors", "dentist", "hospital", "pharmacy", "veterinary"),
    "healthcare": (
        "centre",
        "clinic",
        "dentist",
        "doctor",
        "hospital",
        "laboratory",
        "physiotherapist",
        "psychotherapist",
    ),
    "shop": ("optician", "medical_supply", "hearing_aids"),
}

DEFAULT_USER_AGENT = (
    "local-market-scanner/0.1 (+https://github.com/umutseve4/local-market-scanner)"
)


@dataclass(frozen=True)
class Settings:
    """Runtime settings resolved from the environment."""

    overpass_url: str = DEFAULT_OVERPASS_URL
    request_timeout: int = 180
    user_agent: str = DEFAULT_USER_AGENT
    db_path: Path = field(default_factory=lambda: Path("data/market.sqlite3"))
    google_places_api_key: str | None = None

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            overpass_url=os.getenv("OVERPASS_URL", DEFAULT_OVERPASS_URL),
            request_timeout=int(os.getenv("REQUEST_TIMEOUT", "180")),
            user_agent=os.getenv("USER_AGENT", DEFAULT_USER_AGENT),
            db_path=Path(os.getenv("DB_PATH", "data/market.sqlite3")),
            google_places_api_key=os.getenv("GOOGLE_PLACES_API_KEY") or None,
        )
