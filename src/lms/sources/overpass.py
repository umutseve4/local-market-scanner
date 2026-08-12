"""OpenStreetMap Overpass API data source.

Why OSM and not Google Maps scraping:
  * OSM data is published under ODbL and is explicitly reusable.
  * Scraping Google Maps HTML violates the Google Maps/Google Earth Terms of
    Service. If you want Google data, use the official Places API with your
    own key and stay inside its quota and caching rules.

This module only performs read-only HTTP calls against a public API.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable
from typing import Any

import requests

from ..config import HEALTH_FILTERS, Settings
from ..errors import OverpassResponseError, OverpassUnavailableError
from ..models import Business, normalise_phone, normalise_website

logger = logging.getLogger(__name__)

# Status codes that are worth retrying: rate limiting and gateway/server errors.
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

_SOCIAL_TAGS = (
    "contact:instagram",
    "contact:facebook",
    "contact:twitter",
    "instagram",
    "facebook",
)


def build_query(
    bbox: tuple[float, float, float, float],
    filters: dict[str, Iterable[str]] | None = None,
    timeout: int = 180,
) -> str:
    """Build an Overpass QL query for the given bounding box and tag filters."""
    filters = filters or HEALTH_FILTERS
    south, west, north, east = bbox
    bbox_str = f"{south},{west},{north},{east}"
    clauses: list[str] = []
    for key, values in filters.items():
        joined = "|".join(values)
        for element in ("node", "way"):
            clauses.append(f'  {element}["{key}"~"^({joined})$"]({bbox_str});')
    body = "\n".join(clauses)
    return f"[out:json][timeout:{timeout}];\n(\n{body}\n);\nout center tags;"


def parse_element(element: dict[str, Any]) -> Business | None:
    """Convert a raw Overpass element into a Business, or None if unusable."""
    tags = element.get("tags") or {}
    name = (tags.get("name") or "").strip()
    if not name:
        return None

    category = (
        tags.get("healthcare") or tags.get("amenity") or tags.get("shop") or "unknown"
    )

    center = element.get("center") or {}
    lat = element.get("lat", center.get("lat"))
    lon = element.get("lon", center.get("lon"))

    address_parts = [
        tags.get("addr:street"),
        tags.get("addr:housenumber"),
        tags.get("addr:neighbourhood"),
        tags.get("addr:city"),
    ]
    address = " ".join(p for p in address_parts if p) or None

    social = next((tags[t] for t in _SOCIAL_TAGS if tags.get(t)), None)

    return Business(
        source="osm",
        source_id=f"{element.get('type', 'node')}/{element.get('id')}",
        name=name,
        category=category,
        lat=float(lat) if lat is not None else None,
        lon=float(lon) if lon is not None else None,
        address=address,
        district=tags.get("addr:district") or tags.get("addr:city"),
        phone=normalise_phone(tags.get("phone") or tags.get("contact:phone")),
        website=normalise_website(
            tags.get("website") or tags.get("contact:website") or tags.get("url")
        ),
        email=tags.get("email") or tags.get("contact:email"),
        opening_hours=tags.get("opening_hours"),
        social_url=normalise_website(social),
        raw_tags=tags,
    )


def parse_response(payload: dict[str, Any]) -> list[Business]:
    """Parse a full Overpass JSON response into Business objects.

    Raises:
        OverpassResponseError: if the payload is not a mapping with ``elements``.
    """
    if not isinstance(payload, dict):
        raise OverpassResponseError(
            f"Overpass payload must be a JSON object, got {type(payload).__name__}."
        )
    if "elements" not in payload:
        remark = payload.get("remark") if isinstance(payload, dict) else None
        detail = f" Remark: {remark}" if remark else ""
        raise OverpassResponseError(f"Overpass payload has no 'elements' key.{detail}")
    if not isinstance(payload["elements"], list):
        raise OverpassResponseError("Overpass 'elements' must be a list.")

    businesses: list[Business] = []
    for element in payload.get("elements", []):
        business = parse_element(element)
        if business is not None:
            businesses.append(business)
    return businesses


def _retry_delay(
    response: requests.Response | None, attempt: int, base: float
) -> float:
    """Honour ``Retry-After`` when present, otherwise use exponential backoff."""
    if response is not None:
        header = response.headers.get("Retry-After")
        if header:
            try:
                return max(0.0, float(header))
            except ValueError:
                logger.debug("Unparsable Retry-After header: %r", header)
    return base * (2 ** (attempt - 1))


def _post_once(
    http: requests.Session,
    url: str,
    query: str,
    settings: Settings,
) -> requests.Response:
    """Perform a single POST against one Overpass endpoint."""
    return http.post(
        url,
        data={"data": query},
        headers={"User-Agent": settings.user_agent},
        timeout=settings.request_timeout,
        verify=settings.ca_bundle or True,
    )


def fetch_raw(
    bbox: tuple[float, float, float, float],
    settings: Settings | None = None,
    session: requests.Session | None = None,
    sleep: Any = time.sleep,
) -> dict[str, Any]:
    """Fetch the raw Overpass JSON payload, with retries and mirror fallback.

    Every endpoint in ``settings.endpoints`` is tried in order. Each endpoint
    gets ``settings.max_retries`` attempts with exponential backoff, and
    ``Retry-After`` is respected when the server sends it.

    Raises:
        OverpassUnavailableError: when every endpoint fails.
    """
    settings = settings or Settings.from_env()
    query = build_query(bbox, timeout=settings.request_timeout)
    http = session or requests.Session()
    failures: list[str] = []

    for url in settings.endpoints:
        for attempt in range(1, settings.max_retries + 1):
            logger.info("Querying Overpass at %s (attempt %d)", url, attempt)
            response: requests.Response | None = None
            try:
                response = _post_once(http, url, query, settings)
                if response.status_code in RETRYABLE_STATUS:
                    raise requests.HTTPError(
                        f"HTTP {response.status_code}", response=response
                    )
                response.raise_for_status()
                return response.json()
            except ValueError as exc:  # JSON decode failure
                failures.append(f"{url}: invalid JSON ({exc})")
                logger.warning("Invalid JSON from %s: %s", url, exc)
                break  # a malformed body will not fix itself on retry
            except requests.RequestException as exc:
                failures.append(f"{url}: {exc}")
                logger.warning(
                    "Overpass attempt %d failed for %s: %s", attempt, url, exc
                )
                if attempt < settings.max_retries:
                    delay = _retry_delay(response, attempt, settings.backoff_seconds)
                    logger.info("Retrying in %.1fs", delay)
                    sleep(delay)

    raise OverpassUnavailableError(
        "All Overpass endpoints failed:\n  " + "\n  ".join(failures)
    )


def fetch(
    bbox: tuple[float, float, float, float],
    settings: Settings | None = None,
    session: requests.Session | None = None,
) -> list[Business]:
    """Fetch and parse health facilities inside ``bbox`` from the Overpass API."""
    payload = fetch_raw(bbox, settings=settings, session=session)
    businesses = parse_response(payload)
    logger.info("Parsed %d businesses from Overpass", len(businesses))
    return businesses


def check_status(
    settings: Settings | None = None,
    session: requests.Session | None = None,
) -> list[tuple[str, bool, str]]:
    """Probe every configured endpoint with a tiny query.

    Returns one ``(url, ok, detail)`` tuple per endpoint. This never raises, so
    the ``doctor`` command can report a full picture instead of the first error.
    """
    settings = settings or Settings.from_env()
    http = session or requests.Session()
    tiny = "[out:json][timeout:10];node(1);out ids;"
    results: list[tuple[str, bool, str]] = []
    for url in settings.endpoints:
        try:
            response = _post_once(http, url, tiny, settings)
            ok = response.status_code == 200
            results.append((url, ok, f"HTTP {response.status_code}"))
        except requests.RequestException as exc:
            results.append((url, False, f"{type(exc).__name__}: {exc}"))
    return results
