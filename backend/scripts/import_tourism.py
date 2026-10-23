"""Odisha tourism seed import pipeline.

Reads ``backend/app/data/tourism_seed_*.jsonl``, optionally enriches each record
with coordinates and OSM attribution from Nominatim (1 request/second), validates
fields and duplicates, and upserts rows into SQLite.

Usage (from the project root):
    python -m backend.scripts.import_tourism --geocode
    python -m backend.scripts.import_tourism --geocode --limit 5

Only OpenStreetMap data is used to confirm coordinates. Tourism facts such as
opening hours and ticket prices are NOT inferred: they stay blank ("Not
verified") until a human confirms a cited source.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

import httpx

# Allow ``python backend/scripts/import_tourism.py`` as well as ``-m``.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import settings  # noqa: E402
from backend.app.data.categories import CATEGORY_BY_SLUG  # noqa: E402
from backend.app.database import SessionLocal, init_db  # noqa: E402
from backend.app.models import ImportLog, TourismDestination  # noqa: E402

DATA_DIR = PROJECT_ROOT / "backend" / "app" / "data"
CACHE_PATH = PROJECT_ROOT / "data" / "cache" / "nominatim.json"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

REQUIRED_FIELDS = ("name", "category", "district", "query")


def slugify(value: str) -> str:
    value = value.lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return re.sub(r"-{2,}", "-", value)


def load_seed_files() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(DATA_DIR.glob("tourism_seed_*.jsonl")):
        with path.open(encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise SystemExit(f"Invalid JSON in {path.name} line {line_no}: {exc}") from exc
                record["_source_file"] = path.name
                records.append(record)
    return records


def validate(record: dict[str, Any], seen_names: set[str], seen_slugs: set[str]) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if not record.get(field):
            errors.append(f"missing required field '{field}'")
    category = record.get("category")
    if category and category not in CATEGORY_BY_SLUG:
        errors.append(f"unknown category '{category}'")
    if record.get("latitude") is not None:
        lat = float(record["latitude"])
        if not -90 <= lat <= 90:
            errors.append("latitude out of range")
    if record.get("longitude") is not None:
        lon = float(record["longitude"])
        if not -180 <= lon <= 180:
            errors.append("longitude out of range")
    name_key = (record.get("name") or "").strip().lower()
    slug = slugify(record.get("name") or "")
    if name_key in seen_names:
        errors.append("duplicate name")
    if slug in seen_slugs:
        errors.append("duplicate slug")
    description = record.get("description") or ""
    if len(description) > 4000:
        errors.append("description too long")
    return errors


def geocode(record: dict[str, Any], client: httpx.Client, cache: dict[str, Any]) -> None:
    """Populate lat/lon/osm metadata from Nominatim, using a local cache."""
    query = record.get("query") or record["name"]
    if query in cache:
        cached = cache[query]
    else:
        # Nominatim matches official OSM names, which sometimes differ from the
        # common name. Try progressively simpler queries before giving up.
        variants = [
            query,
            f"{record['name']}, {record.get('district', '')} Odisha",
            f"{record['name']} Odisha",
        ]
        cached = None
        for candidate in dict.fromkeys(v.strip(", ") for v in variants):
            response = client.get(
                NOMINATIM_URL,
                params={"q": candidate, "format": "jsonv2", "limit": 1, "countrycodes": "in"},
            )
            if response.status_code in {403, 429}:
                raise httpx.HTTPStatusError(
                    f"Nominatim refused the request ({response.status_code}). "
                    "Check NOMINATIM_USER_AGENT and the 1 request/second policy.",
                    request=response.request,
                    response=response,
                )
            response.raise_for_status()
            results = response.json()
            time.sleep(1.05)  # Nominatim usage policy: max 1 request/second
            if results:
                cached = results[0]
                break
        cache[query] = cached
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    if not cached:
        record["geocode_error"] = "No Nominatim match"
        return
    record["latitude"] = float(cached["lat"])
    record["longitude"] = float(cached["lon"])
    record["osm_id"] = f"{cached.get('osm_type', 'node')}/{cached.get('osm_id', '')}"
    record["source_url"] = (
        f"https://www.openstreetmap.org/{cached.get('osm_type', 'node')}/{cached.get('osm_id', '')}"
    )
    record["source_name"] = "OpenStreetMap via Nominatim"
    record["licence_information"] = "© OpenStreetMap contributors, ODbL 1.0"
    record["resolved_address"] = cached.get("display_name")
    record["last_verified_at"] = date.today().isoformat()


def upsert(record: dict[str, Any], db) -> str:
    slug = slugify(record["name"])
    existing = db.query(TourismDestination).filter(TourismDestination.slug == slug).one_or_none()
    payload = {
        "name": record["name"],
        "category": record["category"],
        "destination_type": record.get("destination_type"),
        "description": record.get("description"),
        "significance": record.get("significance"),
        "address": record.get("address") or record.get("resolved_address"),
        "locality": record.get("locality"),
        "city": record.get("city"),
        "district": record.get("district"),
        "latitude": record.get("latitude"),
        "longitude": record.get("longitude"),
        "visiting_hours": record.get("visiting_hours"),
        "closed_days": record.get("closed_days"),
        "entry_fee": record.get("entry_fee"),
        "estimated_visit_minutes": record.get("estimated_visit_minutes"),
        "facilities": json.dumps(record["facilities"]) if record.get("facilities") else None,
        "accessibility_information": record.get("accessibility_information"),
        "photography_policy": record.get("photography_policy"),
        "dress_code": record.get("dress_code"),
        "visitor_guidelines": record.get("visitor_guidelines"),
        "official_website": record.get("official_website"),
        "contact_information": record.get("contact_information"),
        "image_reference": record.get("image_reference"),
        "image_credit": record.get("image_credit"),
        "image_licence": record.get("image_licence"),
        "source_url": record.get("source_url"),
        "source_name": record.get("source_name"),
        "licence_information": record.get("licence_information"),
        "last_verified_at": (
            date.fromisoformat(record["last_verified_at"])
            if record.get("last_verified_at")
            else None
        ),
        "verification_status": record.get("verification_status", "provisional"),
        "featured": bool(record.get("featured", False)),
        "tags": record.get("tags"),
        "osm_id": record.get("osm_id"),
    }
    if existing:
        for key, value in payload.items():
            # Never overwrite a human-verified field with a blank import value.
            if value is None and existing.verification_status == "verified":
                continue
            setattr(existing, key, value)
        return "updated"
    db.add(TourismDestination(slug=slug, **payload))
    return "imported"


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Odisha tourism seed data")
    parser.add_argument(
        "--geocode",
        action="store_true",
        help="Look up coordinates on Nominatim (1 request/second, cached).",
    )
    parser.add_argument("--limit", type=int, default=0, help="Import at most N records (testing).")
    parser.add_argument(
        "--allow-missing-coords",
        action="store_true",
        help="Import records even when geocoding fails (map will omit them).",
    )
    args = parser.parse_args()

    records = load_seed_files()
    if args.limit:
        records = records[: args.limit]
    print(f"Loaded {len(records)} seed records from {DATA_DIR}")

    init_db()
    db = SessionLocal()
    stats = {"imported": 0, "updated": 0, "skipped": 0}
    errors: list[str] = []
    seen_names: set[str] = set()
    seen_slugs: set[str] = set()
    resolved: list[dict[str, Any]] = []

    try:
        cache: dict[str, Any] = {}
        if CACHE_PATH.exists():
            cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))

        headers = {"User-Agent": settings.nominatim_user_agent}
        with httpx.Client(timeout=30, headers=headers) as client:
            for record in records:
                if args.geocode and record.get("latitude") is None:
                    try:
                        geocode(record, client, cache)
                    except httpx.HTTPError as exc:
                        record["geocode_error"] = f"Geocoding failed: {exc}"
                    if record.get("geocode_error"):
                        print(f"  ! {record['name']}: {record['geocode_error']}")

                problems = validate(record, seen_names, seen_slugs)
                if record.get("latitude") is None and not args.allow_missing_coords:
                    problems.append("missing coordinates (run with --geocode or --allow-missing-coords)")

                if problems:
                    stats["skipped"] += 1
                    message = f"Skipped {record.get('name')}: {', '.join(problems)}"
                    print("  " + message)
                    errors.append(message)
                    continue

                seen_names.add(record["name"].strip().lower())
                seen_slugs.add(slugify(record["name"]))
                resolved.append(record)
                outcome = upsert(record, db)
                stats[outcome] += 1
                print(f"  {outcome:8s} {record['name']}")

        db.add(
            ImportLog(
                source_file=", ".join(sorted({r['_source_file'] for r in resolved})) or "none",
                imported=stats["imported"],
                updated=stats["updated"],
                skipped=stats["skipped"],
                errors="\n".join(errors)[:4000] or None,
            )
        )
        db.commit()
    finally:
        db.close()

    print(
        f"Done: {stats['imported']} imported, {stats['updated']} updated, "
        f"{stats['skipped']} skipped."
    )
    if args.geocode:
        print(f"Geocode cache: {CACHE_PATH.relative_to(PROJECT_ROOT)}")
    return 0 if stats["imported"] or stats["updated"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
