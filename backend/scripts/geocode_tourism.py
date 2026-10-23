"""One-off helper that enriches the committed tourism seed with OSM coordinates.

The enriched seed is committed so a fresh clone can be seeded without network
access. Re-run this only when adding new seed rows:

    python -m backend.scripts.geocode_tourism

Coordinates come from Photon/Nominatim (OpenStreetMap data) and are validated
against Odisha's bounds and the stated city. A place with no confident match is
left without coordinates instead of being pinned in the wrong location.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import settings  # noqa: E402
from backend.app.services.geo import ODISHA_DISTRICTS, haversine_km  # noqa: E402
from backend.app.services.geocoding import geocode_record, load_cache  # noqa: E402
from backend.scripts.import_tourism import DATA_DIR, load_seed_files  # noqa: E402

# Known-bad Nominatim matches corrected during development. Keeping an explicit
# list documents why they were removed rather than silently trusting a geocoder.
MANUAL_CLEAR = {
    "Lokanath Temple",
    "Ramachandi Temple",
    "Maa Tarini Temple",
    "Raghurajpur Heritage Craft Village",
}


def main() -> int:
    cache = load_cache()
    records = load_seed_files()

    for record in records:
        if record["name"] in MANUAL_CLEAR:
            record["latitude"] = None
            record["longitude"] = None
        # Drop coordinates implausibly far from the stated district centroid.
        if record.get("latitude") is not None and record.get("district") in ODISHA_DISTRICTS:
            distance = haversine_km(
                record["latitude"],
                record["longitude"],
                *ODISHA_DISTRICTS[record["district"]],
            )
            if distance > 150:
                print(f"Clearing far-off pin for {record['name']} ({distance:.0f} km)")
                record["latitude"] = None
                record["longitude"] = None

    missing = [r for r in records if r.get("latitude") is None]
    print(f"{len(records)} records, {len(missing)} need coordinates")

    with httpx.Client(timeout=25, headers={"User-Agent": settings.nominatim_user_agent}) as client:
        for record in missing:
            print(f"Geocoding {record['name']} ...", flush=True)
            try:
                result = geocode_record(client, record, cache)
            except httpx.HTTPError as exc:
                print(f"  failed: {exc}")
                continue
            if not result:
                print("  no confident match (left blank)")
                continue

            record["latitude"] = round(result.latitude, 6)
            record["longitude"] = round(result.longitude, 6)
            if result.osm_type and result.osm_id:
                record["osm_id"] = f"{result.osm_type}/{result.osm_id}"
                record["source_url"] = (
                    f"https://www.openstreetmap.org/{result.osm_type}/{result.osm_id}"
                )
            record["source_name"] = result.source
            record["licence_information"] = "© OpenStreetMap contributors, ODbL 1.0"
            record["last_verified_at"] = "2026-10-23"
            print(f"  -> {record['latitude']:.5f}, {record['longitude']:.5f} | {result.display_name[:70]}")

    by_file: dict[str, list[dict]] = {}
    for record in records:
        by_file.setdefault(record["_source_file"], []).append(record)

    for filename, rows in by_file.items():
        path = DATA_DIR / filename
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                row.pop("_source_file", None)
                row.pop("resolved_address", None)
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"Wrote {path.name} ({len(rows)} rows)")

    with_coords = sum(1 for r in records if r.get("latitude") is not None)
    print(f"{with_coords}/{len(records)} records now have coordinates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
