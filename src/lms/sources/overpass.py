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
from collections.abc import Iterable
from typing import Any

import requests

from ..config import HEALTH_FILTERS, Settings
from ..models import Business, normalise_phone, normalise_website

logger = logging.getLogger(__name__)

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
    """Parse a full Overpass JSON response into Business objects."""
    businesses: list[Business] = []
    for element in payload.get("elements", []):
        business = parse_element(element)
        if business is not None:
            businesses.append(business)
    return businesses


def fetch(
    bbox: tuple[float, float, float, float],
    settings: Settings | None = None,
    session: requests.Session | None = None,
) -> list[Business]:
    """Fetch health facilities inside ``bbox`` from the Overpass API."""
    settings = settings or Settings.from_env()
    query = build_query(bbox, timeout=settings.request_timeout)
    http = session or requests.Session()
    logger.info("Querying Overpass at %s", settings.overpass_url)
    response = http.post(
        settings.overpass_url,
        data={"data": query},
        headers={"User-Agent": settings.user_agent},
        timeout=settings.request_timeout,
    )
    response.raise_for_status()
    businesses = parse_response(response.json())
    logger.info("Parsed %d businesses from Overpass", len(businesses))
    return businesses
