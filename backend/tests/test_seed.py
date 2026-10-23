"""Committed seed data: it must load, be idempotent and stay internally consistent."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select

from backend.app import models
from backend.app.data.categories import CATEGORY_BY_SLUG
from backend.app.seed import DATA_DIR, seed_all, seed_destinations, seed_species

SPECIES_FILE = DATA_DIR / "species_seed.json"
TOURISM_FILES = sorted(DATA_DIR.glob("tourism_seed_*.jsonl"))


def test_species_seed_file_is_valid_json():
    records = json.loads(SPECIES_FILE.read_text(encoding="utf-8"))
    assert records
    for record in records:
        assert {"common_name", "scientific_name", "category"} <= set(record)
        assert record["category"] in {"plant", "bird"}


def test_tourism_seed_rows_use_known_categories():
    assert TOURISM_FILES, "expected at least one tourism seed file"
    for path in TOURISM_FILES:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            assert record["name"], path
            # Unknown categories would be silently dropped during import.
            assert record["category"] in CATEGORY_BY_SLUG, record["name"]


def test_seed_all_inserts_the_catalogue(db):
    summary = seed_all(db, "admin", "test-password")
    assert summary["species_created"] > 0
    assert summary["destinations_created"] > 0
    assert summary["admin_created"] == 1

    assert db.scalar(select(func.count(models.Species.id)))
    assert db.scalar(select(func.count(models.TourismDestination.id)))


def test_seeding_is_idempotent(db):
    seed_all(db, "admin", "test-password")
    second = seed_all(db, "admin", "test-password")
    assert second["species_created"] == 0
    assert second["destinations_created"] == 0
    assert second["admin_created"] == 0


def test_seed_species_is_idempotent_on_its_own(db):
    first = seed_species(db)
    assert first > 0
    assert seed_species(db) == 0


def test_seed_destinations_is_idempotent_on_its_own(db):
    assert seed_destinations(db) > 0
    assert seed_destinations(db) == 0


def test_every_seeded_destination_has_a_unique_slug(db):
    seed_destinations(db)
    slugs = db.scalars(select(models.TourismDestination.slug)).all()
    assert len(slugs) == len(set(slugs))


def test_seeded_coordinates_are_inside_odisha_when_present(db):
    seed_destinations(db)
    rows = db.scalars(
        select(models.TourismDestination).where(
            models.TourismDestination.latitude.is_not(None),
            models.TourismDestination.longitude.is_not(None),
        )
    ).all()
    assert rows
    for row in rows:
        assert 17.0 <= row.latitude <= 23.5, (row.name, row.latitude)
        assert 81.0 <= row.longitude <= 88.0, (row.name, row.longitude)


def test_seeded_species_have_consistent_categories(db):
    seed_species(db)
    for species in db.scalars(select(models.Species)).all():
        assert species.category in {"plant", "bird"}
        assert species.common_name.strip()
        assert species.scientific_name.strip()
