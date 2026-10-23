"""Health, live statistics, home dashboard data and the unified map."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from ..data.categories import CATEGORY_BY_SLUG, CATEGORY_GROUPS, TOURISM_CATEGORIES
from ..database import get_db
from ..models import BiodiversityObservation, Species, TourismDestination
from ..schemas import (
    CategoryOut,
    DestinationBase,
    DistrictOut,
    MapDestination,
    MapLayerOut,
    MapObservation,
    ObservationOut,
    SpeciesOut,
    StatsOut,
)
from ..services.geo import ODISHA_DISTRICTS, obscure_coordinates
from ..services.predictor import registry

router = APIRouter(prefix="/api", tags=["Platform"])


@router.get("/health")
def health(db: Annotated[Session, Depends(get_db)]):
    database_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - health check must never raise
        database_ok = False
    model_status = registry.status()
    return {
        "status": "ok" if database_ok else "degraded",
        "database": "connected" if database_ok else "unavailable",
        "ai_models": {
            "plant": model_status["plant"]["available"],
            "bird": model_status["bird"]["available"],
        },
        "torch_installed": model_status["torch_installed"],
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/stats", response_model=StatsOut)
def stats(db: Annotated[Session, Depends(get_db)]):
    destinations_total = db.scalar(select(func.count(TourismDestination.id))) or 0
    destinations_verified = db.scalar(
        select(func.count(TourismDestination.id)).where(
            TourismDestination.verification_status == "verified"
        )
    ) or 0
    districts_covered = db.scalar(
        select(func.count(func.distinct(TourismDestination.district))).where(
            TourismDestination.district.is_not(None)
        )
    ) or 0
    categories_covered = db.scalar(
        select(func.count(func.distinct(TourismDestination.category)))
    ) or 0
    observations_total = db.scalar(
        select(func.count(BiodiversityObservation.id)).where(
            BiodiversityObservation.consented.is_(True)
        )
    ) or 0
    observations_verified = db.scalar(
        select(func.count(BiodiversityObservation.id)).where(
            BiodiversityObservation.consented.is_(True),
            BiodiversityObservation.verification_status == "verified",
        )
    ) or 0
    species_catalogued = db.scalar(select(func.count(Species.id))) or 0
    plant_species = db.scalar(
        select(func.count(Species.id)).where(Species.category == "plant")
    ) or 0
    bird_species = db.scalar(
        select(func.count(Species.id)).where(Species.category == "bird")
    ) or 0
    model_status = registry.status()
    return StatsOut(
        destinations_total=destinations_total,
        destinations_verified=destinations_verified,
        districts_covered=districts_covered,
        categories_covered=categories_covered,
        observations_total=observations_total,
        observations_verified=observations_verified,
        species_catalogued=species_catalogued,
        plant_species=plant_species,
        bird_species=bird_species,
        model_available=model_status["plant"]["available"] or model_status["bird"]["available"],
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/home")
def home(db: Annotated[Session, Depends(get_db)]):
    """Everything the landing page needs in one call (all values live)."""
    stats_payload = stats(db)
    category_counts = dict(
        db.execute(
            select(TourismDestination.category, func.count(TourismDestination.id)).group_by(
                TourismDestination.category
            )
        ).all()
    )
    featured = db.scalars(
        select(TourismDestination)
        .where(TourismDestination.featured.is_(True))
        .order_by(TourismDestination.name)
        .limit(6)
    ).all()
    recent = db.scalars(
        select(BiodiversityObservation)
        .where(BiodiversityObservation.consented.is_(True))
        .order_by(BiodiversityObservation.created_at.desc())
        .limit(4)
    ).all()
    map_points = db.scalars(
        select(TourismDestination)
        .where(
            TourismDestination.latitude.is_not(None),
            TourismDestination.longitude.is_not(None),
        )
        .order_by(TourismDestination.featured.desc())
        .limit(60)
    ).all()
    species = db.scalars(
        select(Species).order_by(Species.category, Species.common_name)
    ).all()
    return {
        "stats": stats_payload.model_dump(),
        "featured": [DestinationBase.model_validate(item).model_dump() for item in featured],
        "recent_observations": [
            {
                "id": item.id,
                "label": item.predicted_common_name or item.predicted_species,
                "scientific_name": item.predicted_species,
                "category": item.category,
                "confidence": item.confidence_score,
                "status": item.verification_status,
                "district": item.district,
                "created_at": item.created_at.isoformat(),
            }
            for item in recent
        ],
        "categories": [
            {
                **category,
                "count": int(category_counts.get(category["slug"], 0)),
            }
            for category in TOURISM_CATEGORIES
        ],
        "groups": CATEGORY_GROUPS,
        "map_preview": [
            {
                "id": item.id,
                "name": item.name,
                "slug": item.slug,
                "category": item.category,
                "latitude": item.latitude,
                "longitude": item.longitude,
            }
            for item in map_points
        ],
        "species": [SpeciesOut.model_validate(item).model_dump() for item in species],
    }


@router.get("/map", response_model=MapLayerOut)
def unified_map(
    db: Annotated[Session, Depends(get_db)],
    layers: Annotated[
        str, Query(pattern="^(tourism|biodiversity|combined)(,(tourism|biodiversity))*$")
    ] = "combined",
    district: str | None = None,
    category: Annotated[list[str] | None, Query()] = None,
    status_filter: Annotated[
        Literal["pending", "verified", "rejected", "needs_review"] | None,
        Query(alias="status"),
    ] = None,
    start_date: date | None = None,
    end_date: date | None = None,
    include_observations: bool = True,
):
    active = set(layers.split(","))
    want_tourism = include_observations and bool({"tourism", "combined"} & active)
    want_biodiversity = include_observations and bool({"biodiversity", "combined"} & active)

    destinations: list[MapDestination] = []
    observations: list[MapObservation] = []
    notes = []

    if want_tourism:
        statement = select(TourismDestination).where(
            TourismDestination.latitude.is_not(None),
            TourismDestination.longitude.is_not(None),
        )
        if district:
            statement = statement.where(TourismDestination.district == district)
        if category:
            statement = statement.where(TourismDestination.category.in_(category))
        for item in db.scalars(statement.order_by(TourismDestination.name)).all():
            destinations.append(
                MapDestination(
                    id=item.id,
                    name=item.name,
                    slug=item.slug,
                    category=item.category,
                    district=item.district,
                    city=item.city,
                    latitude=item.latitude,
                    longitude=item.longitude,
                    featured=item.featured,
                    verification_status=item.verification_status,
                )
            )
        notes.append(
            f"{len(destinations)} tourism destinations with verified coordinates."
        )

    if want_biodiversity:
        statement = select(BiodiversityObservation).where(
            BiodiversityObservation.consented.is_(True),
            BiodiversityObservation.latitude.is_not(None),
            BiodiversityObservation.longitude.is_not(None),
        )
        if district:
            statement = statement.where(BiodiversityObservation.district == district)
        if category:
            statement = statement.where(BiodiversityObservation.category.in_(category))
        if status_filter:
            statement = statement.where(
                BiodiversityObservation.verification_status == status_filter
            )
        if start_date:
            statement = statement.where(
                func.date(BiodiversityObservation.created_at) >= start_date
            )
        if end_date:
            statement = statement.where(
                func.date(BiodiversityObservation.created_at) <= end_date
            )
        for item in db.scalars(statement).all():
            lat, lon, precision = obscure_coordinates(
                item.latitude, item.longitude, item.location_precision, item.derived_sensitive
            )
            observations.append(
                MapObservation(
                    id=item.id,
                    label=item.predicted_common_name or item.predicted_species,
                    category=item.category,
                    verification_status=item.verification_status,
                    latitude=lat,
                    longitude=lon,
                    location_precision=precision,
                    created_at=item.created_at,
                    obscured=precision != "exact",
                )
            )
        notes.append(
            f"{len(observations)} consented biodiversity observations with coordinates. "
            "Sensitive records are shown at reduced precision."
        )

    all_lats = [d.latitude for d in destinations] + [o.latitude for o in observations]
    all_lons = [d.longitude for d in destinations] + [o.longitude for o in observations]
    bounds = (
        {
            "min_lat": min(all_lats),
            "max_lat": max(all_lats),
            "min_lon": min(all_lons),
            "max_lon": max(all_lons),
        }
        if all_lats
        else None
    )
    return MapLayerOut(
        destinations=destinations,
        observations=observations,
        bounds=bounds,
        notes=" ".join(notes)
        or "No records match the selected layers and filters.",
    )


@router.get("/districts")
def districts(db: Annotated[Session, Depends(get_db)]):
    rows = db.execute(
        select(TourismDestination.district, func.count(TourismDestination.id))
        .where(TourismDestination.district.is_not(None))
        .group_by(TourismDestination.district)
        .order_by(TourismDestination.district)
    ).all()
    counts = {name: int(count) for name, count in rows}
    known = [
        DistrictOut(name=name, count=counts.get(name, 0))
        for name in sorted(ODISHA_DISTRICTS)
    ]
    extra = [
        DistrictOut(name=name, count=count)
        for name, count in sorted(counts.items())
        if name not in ODISHA_DISTRICTS
    ]
    return {"odisha": known + extra, "with_records": len(counts)}


@router.get("/taxonomy")
def taxonomy(db: Annotated[Session, Depends(get_db)]):
    """Category + species reference data used by forms and legends."""
    counts = dict(
        db.execute(
            select(TourismDestination.category, func.count(TourismDestination.id)).group_by(
                TourismDestination.category
            )
        ).all()
    )
    species = db.scalars(select(Species).order_by(Species.category, Species.common_name)).all()
    return {
        "categories": [
            CategoryOut(**category, count=int(counts.get(category["slug"], 0))).model_dump()
            for category in TOURISM_CATEGORIES
        ],
        "groups": CATEGORY_GROUPS,
        "species": [SpeciesOut.model_validate(item).model_dump() for item in species],
        "districts": sorted(ODISHA_DISTRICTS),
        "legend": {
            "tourism": {slug: CATEGORY_BY_SLUG[slug]["label"] for slug in CATEGORY_BY_SLUG},
            "biodiversity": {
                "plant": "Plant observation",
                "bird": "Bird observation",
                "pending": "Awaiting review",
                "verified": "Human verified",
                "needs_review": "Needs review",
            },
        },
    }
