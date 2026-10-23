"""Pytest fixtures for the BioTrace API.

The environment is configured *before* ``backend.app`` is imported so the whole
suite runs against an isolated temporary SQLite database, upload directory and
model directory. Nothing here touches the developer's real ``data/biotrace.db``.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

_TMP_ROOT = Path(tempfile.mkdtemp(prefix="prakritipath-tests-"))

os.environ["BIOTRACE_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP_ROOT / 'test.db').as_posix()}"
os.environ["UPLOAD_DIR"] = str(_TMP_ROOT / "uploads")
os.environ["MODEL_DIR"] = str(_TMP_ROOT / "models")
os.environ["BIOTRACE_SECRET_KEY"] = "test-only-secret-key-do-not-use-in-production"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "test-password"
os.environ["ADMIN_TOKEN_TTL_MINUTES"] = "60"
os.environ["WIKIPEDIA_ENRICHMENT"] = "0"
os.environ["MAX_UPLOAD_MB"] = "8"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.app import models  # noqa: E402
from backend.app.database import Base, SessionLocal, engine  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.rate_limit import auth_limiter, upload_limiter, write_limiter  # noqa: E402

SESSION_HEADERS = {"X-Session-Id": "test-session-0001"}


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    shutil.rmtree(_TMP_ROOT, ignore_errors=True)


@pytest.fixture(autouse=True)
def isolated_schema():
    """Give every test a clean schema and fresh rate-limit windows."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    upload_limiter.reset()
    auth_limiter.reset()
    write_limiter.reset()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    # Deliberately not used as a context manager: the app lifespan seeds the
    # real catalogue, which tests don't need.
    return TestClient(app)


@pytest.fixture()
def destination(db) -> models.TourismDestination:
    item = models.TourismDestination(
        name="Barabati Fort",
        slug="barabati-fort",
        category="fort_palace",
        destination_type="Fort",
        description="A medieval fort in Cuttack.",
        city="Cuttack",
        district="Cuttack",
        state="Odisha",
        latitude=20.4847,
        longitude=85.8649,
        estimated_visit_minutes=60,
        verification_status="verified",
        featured=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@pytest.fixture()
def species(db) -> models.Species:
    item = models.Species(
        common_name="Indian Peafowl",
        scientific_name="Pavo cristatus",
        category="bird",
        known_regions="IN-OR",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@pytest.fixture()
def observation(db, species) -> models.BiodiversityObservation:
    item = models.BiodiversityObservation(
        species_id=species.id,
        predicted_species=species.scientific_name,
        predicted_common_name=species.common_name,
        category="bird",
        confidence_score=0.91,
        image_path="observations/2026/01/test.jpg",
        image_quality_status="good",
        latitude=20.2961,
        longitude=85.8245,
        location_precision="exact",
        district="Khordha",
        verification_status="pending",
        consented=True,
        owner_session_hash=None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
