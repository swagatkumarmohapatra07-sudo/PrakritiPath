"""Geospatial helpers and Odisha district reference data.

Coordinates for districts are approximate administrative centroids used only to
suggest a district for a submitted coordinate. They are NOT survey data.
"""

from __future__ import annotations

import math

# name -> (latitude, longitude) approximate centroid
ODISHA_DISTRICTS: dict[str, tuple[float, float]] = {
    "Angul": (20.8400, 85.1018),
    "Balangir": (20.7010, 83.4840),
    "Balasore": (21.4934, 86.9335),
    "Bargarh": (21.3333, 83.6167),
    "Bhadrak": (21.0574, 86.5155),
    "Boudh": (20.8333, 84.3167),
    "Cuttack": (20.4625, 85.8830),
    "Deogarh": (21.5333, 84.7333),
    "Dhenkanal": (20.8400, 85.5980),
    "Gajapati": (18.9167, 84.1333),
    "Ganjam": (19.3870, 84.7000),
    "Jagatsinghpur": (20.2667, 86.1667),
    "Jajpur": (20.8500, 86.3333),
    "Jharsuguda": (21.8500, 84.0333),
    "Kalahandi": (19.9000, 83.1667),
    "Kandhamal": (20.3000, 84.2000),
    "Kendrapara": (20.5000, 86.4167),
    "Kendujhar": (21.6333, 85.5833),
    "Khordha": (20.2961, 85.8245),
    "Koraput": (18.8135, 82.7120),
    "Malkangiri": (18.3500, 81.8833),
    "Mayurbhanj": (22.0000, 86.6667),
    "Nabarangpur": (19.2333, 82.5500),
    "Nayagarh": (20.1333, 85.1000),
    "Nuapada": (20.8000, 82.5333),
    "Puri": (19.8135, 85.8312),
    "Rayagada": (19.1667, 83.4167),
    "Sambalpur": (21.4669, 83.9812),
    "Subarnapur": (20.8333, 83.9167),
    "Sundargarh": (22.1167, 84.0333),
}

ODISHA_BOUNDS = {"min_lat": 17.7, "max_lat": 22.9, "min_lon": 81.3, "max_lon": 87.6}

# Species distribution is stored as comma separated ISO 3166-2 region codes.
# Only Odisha-level knowledge is available for the demo catalogue, so the check
# is deliberately coarse and never used to claim absence.
REGION_ODISHA = "IN-OR"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def nearest_district(latitude: float, longitude: float) -> tuple[str, float]:
    best_name = "Unknown"
    best_distance = float("inf")
    for name, (lat, lon) in ODISHA_DISTRICTS.items():
        distance = haversine_km(latitude, longitude, lat, lon)
        if distance < best_distance:
            best_name, best_distance = name, distance
    return best_name, round(best_distance, 1)


def in_odisha(latitude: float, longitude: float) -> bool:
    b = ODISHA_BOUNDS
    return b["min_lat"] <= latitude <= b["max_lat"] and b["min_lon"] <= longitude <= b["max_lon"]


def plausibility_check(
    known_regions: str | None,
    district: str | None,
    latitude: float | None,
    longitude: float | None,
) -> dict[str, object]:
    """Soft geographical plausibility check.

    Returns a status plus a message that is careful not to imply proof of
    absence. It only flags a record when the catalogue explicitly lists known
    regions and the submitted location falls outside all of them.
    """
    if latitude is None or longitude is None:
        if district:
            return {
                "status": "plausible",
                "message": (
                    f"District-level location supplied ({district}); precise "
                    "coordinates were not provided, so distance checks are skipped."
                ),
                "district": district,
                "region_code": None,
            }
        return {
            "status": "not_provided",
            "message": (
                "Location verification unavailable. No coordinates or district were "
                "supplied; the prediction is image-only."
            ),
            "district": None,
            "region_code": None,
        }

    region = REGION_ODISHA if in_odisha(latitude, longitude) else None
    resolved_district = district or nearest_district(latitude, longitude)[0]
    if not known_regions:
        return {
            "status": "unavailable",
            "message": (
                "Location verification unavailable: this species has no curated "
                "distribution record yet."
            ),
            "district": resolved_district,
            "region_code": region,
        }

    regions = {part.strip() for part in known_regions.split(",") if part.strip()}
    if region and region in regions:
        return {
            "status": "plausible",
            "message": (
                f"Within the catalogue's recorded region (Odisha). This supports "
                f"plausibility but does not confirm the identification."
            ),
            "district": resolved_district,
            "region_code": region,
        }
    if not region:
        return {
            "status": "outside_known_range",
            "message": (
                "The supplied coordinates fall outside Odisha, while this catalogue "
                "only records species distributions for Odisha. Geographic checks are "
                "therefore inconclusive."
            ),
            "district": resolved_district,
            "region_code": None,
        }
    return {
        "status": "outside_known_range",
        "message": (
            "The coordinate is outside this species' curated distribution record. "
            "This can reflect incomplete distribution data, so it is a review flag, "
            "not proof that the species is absent."
        ),
        "district": resolved_district,
        "region_code": region,
    }


def obscure_coordinates(
    latitude: float, longitude: float, precision: str, sensitive: bool
) -> tuple[float, float, str]:
    """Reduce precision for sensitive records.

    Approximate coordinates are snapped to a ~1.1 km grid. Sensitive records are
    additionally snapped to a ~11 km grid and never exposed exactly.
    """
    if precision == "exact" and not sensitive:
        return latitude, longitude, "exact"
    if precision == "approximate" or (precision == "exact" and sensitive):
        step = 0.1 if sensitive else 0.01
        return (
            round(round(latitude / step) * step, 3),
            round(round(longitude / step) * step, 3),
            "approximate",
        )
    return latitude, longitude, precision
