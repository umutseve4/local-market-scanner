"""Configuration loading for local-market-scanner.

Secrets are read from environment variables only. Never hardcode keys.
See .env.example for the expected variable names.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ConfigError

DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Public Overpass instances, tried in order. The main instance is rate limited
# and occasionally returns 429/504; falling back keeps a scan usable.
DEFAULT_OVERPASS_MIRRORS: tuple[str, ...] = (
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)

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
    overpass_mirrors: tuple[str, ...] = DEFAULT_OVERPASS_MIRRORS
    request_timeout: int = 180
    max_retries: int = 3
    backoff_seconds: float = 2.0
    user_agent: str = DEFAULT_USER_AGENT
    db_path: Path = field(default_factory=lambda: Path("data/market.sqlite3"))
    ca_bundle: str | None = None
    # repr=False so that an accidental log/print of Settings never leaks the key.
    google_places_api_key: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.request_timeout <= 0:
            raise ConfigError("REQUEST_TIMEOUT must be a positive integer.")
        if self.max_retries < 1:
            raise ConfigError("MAX_RETRIES must be at least 1.")
        if self.backoff_seconds < 0:
            raise ConfigError("BACKOFF_SECONDS cannot be negative.")
        if not self.overpass_url.startswith(("http://", "https://")):
            raise ConfigError(
                f"OVERPASS_URL must be an http(s) URL, got {self.overpass_url!r}."
            )
        for mirror in self.overpass_mirrors:
            if not mirror.startswith(("http://", "https://")):
                raise ConfigError(
                    f"OVERPASS_MIRRORS entries must be http(s) URLs, got {mirror!r}."
                )

    @property
    def endpoints(self) -> tuple[str, ...]:
        """Primary endpoint first, then any mirror that is not a duplicate."""
        ordered = [self.overpass_url]
        ordered.extend(m for m in self.overpass_mirrors if m != self.overpass_url)
        return tuple(ordered)

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings from environment variables, with documented defaults."""
        mirrors_raw = os.getenv("OVERPASS_MIRRORS", "")
        mirrors = (
            tuple(m.strip() for m in mirrors_raw.split(",") if m.strip())
            if mirrors_raw
            else DEFAULT_OVERPASS_MIRRORS
        )
        return cls(
            overpass_url=os.getenv("OVERPASS_URL", DEFAULT_OVERPASS_URL),
            overpass_mirrors=mirrors,
            request_timeout=_env_int("REQUEST_TIMEOUT", 180),
            max_retries=_env_int("MAX_RETRIES", 3),
            backoff_seconds=_env_float("BACKOFF_SECONDS", 2.0),
            user_agent=os.getenv("USER_AGENT", DEFAULT_USER_AGENT),
            db_path=Path(os.getenv("DB_PATH", "data/market.sqlite3")),
            ca_bundle=(
                os.getenv("REQUESTS_CA_BUNDLE") or os.getenv("CA_BUNDLE") or None
            ),
            google_places_api_key=os.getenv("GOOGLE_PLACES_API_KEY") or None,
        )


def _env_int(name: str, default: int) -> int:
    """Read an int from the environment with a clear error on bad input."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}.") from exc


def _env_float(name: str, default: float) -> float:
    """Read a float from the environment with a clear error on bad input."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}.") from exc
