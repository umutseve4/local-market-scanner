"""Typed exceptions for local-market-scanner.

Having explicit exception types lets the CLI map failures to distinct exit
codes instead of collapsing everything into a generic traceback.
"""

from __future__ import annotations


class LmsError(Exception):
    """Base class for every error raised by this package."""


class ConfigError(LmsError):
    """Raised when configuration values are missing or malformed."""


class SourceError(LmsError):
    """Base class for data-source failures."""


class OverpassUnavailableError(SourceError):
    """Every configured Overpass endpoint failed after all retries."""


class OverpassResponseError(SourceError):
    """The endpoint answered, but the payload is not a usable Overpass result."""
