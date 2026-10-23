"""Idempotent database seeding from the committed JSON/JSONL catalogue."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .data.categories import CATEGORY_BY_SLUG
from .models import AdminUser, Species, TourismDestination
from .security import hash_password, verify_password

DATA_DIR = Path(__file__).resolve().parent / "data"
SPECIES_FILE = DATA_DIR / "species_seed.json"


def seed_species(db: Session) -> int:
    records = json.loads(SPECIES_FILE.read_text(encoding="utf-8"))
    existing = {
        name
        for (name,) in db.execute(select(Species.scientific_name)).all()
    }
    created = 0
    for record in records:
        if record["scientific_name"] in existing:
            continue
        db.add(
            Species(
                common_name=record["common_name"],
                scientific_name=record["scientific_name"],
                category=record["category"],
                description=record.get("description"),
                habitat=record.get("habitat"),
                distribution_information=record.get("distribution_information"),
                known_regions=record.get("known_regions"),
                conservation_status=record.get("conservation_status"),
                source=record.get("source"),
                licence_information=record.get("licence_information"),
            )
        )
        created += 1
    db.commit()
    return created


def seed_destinations(db: Session) -> int:
    """Seed destinations only when the table is empty (safe for repeated boots)."""
    if db.scalar(select(func.count(TourismDestination.id))) or 0:
        return 0

    rows: list[dict] = []
    for path in sorted(DATA_DIR.glob("tourism_seed_*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))

    created = 0
    for record in rows:
        if record.get("category") not in CATEGORY_BY_SLUG:
            continue
        slug = _slug(record["name"])
        db.add(
            TourismDestination(
                name=record["name"],
                slug=slug,
                category=record["category"],
                destination_type=record.get("destination_type"),
                description=record.get("description"),
                significance=record.get("significance"),
                address=record.get("address"),
                locality=record.get("locality"),
                city=record.get("city"),
                district=record.get("district"),
                state="Odisha",
                latitude=record.get("latitude"),
                longitude=record.get("longitude"),
                visiting_hours=record.get("visiting_hours"),
                closed_days=record.get("closed_days"),
                entry_fee=record.get("entry_fee"),
                estimated_visit_minutes=record.get("estimated_visit_minutes"),
                facilities=json.dumps(record["facilities"]) if record.get("facilities") else None,
                accessibility_information=record.get("accessibility_information"),
                photography_policy=record.get("photography_policy"),
                dress_code=record.get("dress_code"),
                visitor_guidelines=record.get("visitor_guidelines"),
                official_website=record.get("official_website"),
                contact_information=record.get("contact_information"),
                image_reference=record.get("image_reference"),
                image_credit=record.get("image_credit"),
                image_licence=record.get("image_licence"),
                source_url=record.get("source_url"),
                source_name=record.get("source_name"),
                licence_information=record.get("licence_information"),
                last_verified_at=(
                    date.fromisoformat(record["last_verified_at"])
                    if record.get("last_verified_at")
                    else None
                ),
                verification_status=record.get("verification_status", "provisional"),
                featured=bool(record.get("featured", False)),
                tags=record.get("tags"),
                osm_id=record.get("osm_id"),
            )
        )
        created += 1
    db.commit()
    return created


def _slug(name: str) -> str:
    import re

    value = name.lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return re.sub(r"-{2,}", "-", value)


def ensure_admin(db: Session, username: str, password: str) -> bool:
    """Create the admin account if it does not exist.

    Returns True when a new account was created. The password is never logged.
    """
    existing = db.scalar(select(AdminUser).where(AdminUser.username == username))
    if existing:
        return False
    db.add(AdminUser(username=username, password_hash=hash_password(password)))
    db.commit()
    return True


def seed_all(db: Session, admin_username: str, admin_password: str) -> dict[str, int]:
    species = seed_species(db)
    destinations = seed_destinations(db)
    admin = ensure_admin(db, admin_username, admin_password)
    return {
        "species_created": species,
        "destinations_created": destinations,
        "admin_created": int(admin),
    }
