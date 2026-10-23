"""Geocoding for the tourism import pipeline.

Primary source: Photon (https://photon.komoot.io), an open-source geocoder built
on OpenStreetMap data. Nominatim is kept as a fallback. Both are used sparingly
and every resolved coordinate is validated against Odisha's bounds and the
record's district before it is accepted.

The resolved data is cached in ``data/cache`` and the enriched seed is committed,
so a fresh clone never needs network access to run the app.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from .geo import ODISHA_BOUNDS, ODISHA_DISTRICTS, haversine_km

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CACHE_PATH = PROJECT_ROOT / "data" / "cache" / "photon.json"

# Approximate city centres used only to disambiguate same-named places.
CITY_CENTRES: dict[str, tuple[float, float]] = {
    "Bhubaneswar": (20.2961, 85.8245),
    "Cuttack": (20.4625, 85.8830),
    "Puri": (19.8135, 85.8312),
    "Konark": (19.8876, 86.0945),
    "Sambalpur": (21.4669, 83.9812),
    "Baripada": (21.9333, 86.7333),
    "Berhampur": (19.3150, 84.7941),
    "Balasore": (21.4934, 86.9335),
    "Banki": (20.3833, 85.5333),
    "Kakatpur": (20.0000, 86.2000),
    "Dhenkanal": (20.8400, 85.5980),
    "Angul": (20.8400, 85.1018),
    "Bargarh": (21.3333, 83.6167),
    "Koraput": (18.8135, 82.7120),
    "Gopalpur": (19.2599, 84.9052),
    "Chandipur": (21.4472, 87.0230),
    "Sambalpur ": (21.4669, 83.9812),
}


@dataclass
class GeocodeResult:
    latitude: float
    longitude: float
    display_name: str
    osm_type: str | None
    osm_id: str | None
    source: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "latitude": round(self.latitude, 6),
            "longitude": round(self.longitude, 6),
            "display_name": self.display_name,
            "osm_type": self.osm_type,
            "osm_id": self.osm_id,
            "source": self.source,
        }


class GeocodeError(RuntimeError):
    pass


def load_cache() -> dict[str, Any]:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


def _score(candidate: dict[str, Any], record: dict[str, Any]) -> float:
    """Score a candidate for plausibility. Lower is better."""

    def normalise(text: str) -> set[str]:
        return {part for part in "".join(c if c.isalnum() else " " for c in text.lower()).split() if part}

    props = candidate.get("properties", {})
    candidate_name = str(props.get("name") or "")
    wanted = normalise(record["name"])
    found = normalise(candidate_name)
    overlap = len(wanted & found) / max(1, len(wanted))
    score = (1.0 - overlap) * 2.0

    lat, lon = candidate["geometry"]["coordinates"][1], candidate["geometry"]["coordinates"][0]
    if not (
        ODISHA_BOUNDS["min_lat"] <= lat <= ODISHA_BOUNDS["max_lat"]
        and ODISHA_BOUNDS["min_lon"] <= lon <= ODISHA_BOUNDS["max_lon"]
    ):
        score += 10

    district = (record.get("district") or "").lower()
    haystack = " ".join(
        str(props.get(key) or "") for key in ("district", "county", "state", "city", "locality")
    ).lower()
    if district and district not in haystack and district.replace(" ", "") not in haystack.replace(" ", ""):
        # Not conclusive: OSM may store the district only on a parent boundary.
        score += 1.0

    city = (record.get("city") or "").strip()
    city_centre = CITY_CENTRES.get(city)
    if city_centre:
        score += min(haversine_km(lat, lon, *city_centre) / 25.0, 4.0)
    return score


def _photon(
    client: httpx.Client, query: str, record: dict[str, Any]
) -> GeocodeResult | None:
    response = client.get(
        "https://photon.komoot.io/api/",
        params={"q": query, "limit": 5, "lang": "en"},
    )
    if response.status_code == 429:
        raise GeocodeError("Photon rate limit reached; wait and retry.")
    response.raise_for_status()
    features = response.json().get("features", [])
    if not features:
        return None
    ranked = sorted(features, key=lambda item: _score(item, record))
    best = ranked[0]
    if _score(best, record) > 4.5:
        return None
    props = best.get("properties", {})
    lon, lat = best["geometry"]["coordinates"][:2]
    return GeocodeResult(
        latitude=lat,
        longitude=lon,
        display_name=", ".join(
            value
            for value in (
                props.get("name"),
                props.get("street"),
                props.get("city"),
                props.get("district"),
                props.get("state"),
                props.get("country"),
            )
            if value
        ),
        osm_type=props.get("osm_type"),
        osm_id=str(props.get("osm_id")) if props.get("osm_id") is not None else None,
        source="OpenStreetMap via Photon",
    )


def _nominatim(
    client: httpx.Client, query: str, record: dict[str, Any]
) -> GeocodeResult | None:
    response = client.get(
        "https://nominatim.openstreetmap.org/search",
        params={
            "q": query,
            "format": "jsonv2",
            "limit": 3,
            "addressdetails": 1,
            "countrycodes": "in",
        },
    )
    if response.status_code in {403, 429}:
        return None
    response.raise_for_status()
    results = response.json()
    if not results:
        return None
    # Reuse the scoring logic by adapting Nominatim's shape.
    adapted = []
    for item in results:
        adapted.append(
            {
                "geometry": {"coordinates": [float(item["lon"]), float(item["lat"])]},
                "properties": {
                    "name": item.get("name"),
                    "city": item.get("address", {}).get("city"),
                    "district": item.get("address", {}).get("state_district"),
                    "state": item.get("address", {}).get("state"),
                },
                "raw": item,
            }
        )
    ranked = sorted(adapted, key=lambda candidate: _score(candidate, record))
    best = ranked[0]
    if _score(best, record) > 4.5:
        return None
    raw = best["raw"]
    return GeocodeResult(
        latitude=float(raw["lat"]),
        longitude=float(raw["lon"]),
        display_name=raw.get("display_name", ""),
        osm_type=raw.get("osm_type"),
        osm_id=str(raw.get("osm_id")) if raw.get("osm_id") is not None else None,
        source="OpenStreetMap via Nominatim",
    )


def geocode_record(
    client: httpx.Client, record: dict[str, Any], cache: dict[str, Any] | None = None
) -> GeocodeResult | None:
    """Geocode one seed record with validation.

    Only returns a result inside Odisha and reasonably close to the stated city
    where a city centre is known. A missing result is preferable to a wrong pin.
    """
    cache = cache if cache is not None else {}
    cache_key = record.get("query") or f"{record['name']}, {record.get('district')}, Odisha"
    if cache_key in cache:
        cached = cache[cache_key]
        return GeocodeResult(**cached) if cached else None

    queries = [
        f"{record['name']}, {record.get('city') or record.get('district')}, Odisha",
        f"{record['name']}, {record.get('district')}, Odisha",
        f"{record['name']} Odisha",
    ]
    result: GeocodeResult | None = None
    for query in dict.fromkeys(queries):
        try:
            result = _photon(client, query, record)
        except httpx.HTTPError:
            result = None
        if result:
            break
        time.sleep(0.35)

    if result is None:
        try:
            result = _nominatim(client, record.get("query") or queries[0], record)
        except httpx.HTTPError:
            result = None
        time.sleep(1.1)

    if result is not None:
        # Final guard: never write coordinates outside Odisha for this dataset.
        if not (
            ODISHA_BOUNDS["min_lat"] <= result.latitude <= ODISHA_BOUNDS["max_lat"]
            and ODISHA_BOUNDS["min_lon"] <= result.longitude <= ODISHA_BOUNDS["max_lon"]
        ):
            result = None

    cache[cache_key] = result.as_dict() if result else None
    save_cache(cache)
    return result


def lookup(record: dict[str, Any], user_agent: str) -> GeocodeResult | None:
    cache = load_cache()
    with httpx.Client(timeout=25, headers={"User-Agent": user_agent}) as client:
        return geocode_record(client, record, cache)
