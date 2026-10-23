"""Tourism discovery API: search, filters, details, map data, suggestions."""

from __future__ import annotations

import json
import math
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..data.categories import CATEGORY_BY_SLUG, TOURISM_CATEGORIES
from ..database import get_db
from ..models import ReviewReport, TourismDestination
from ..rate_limit import client_key, write_limiter
from ..schemas import (
    CategoryOut,
    CorrectionCreate,
    DestinationBase,
    DestinationListOut,
    DestinationNearby,
    DestinationOut,
    DistrictOut,
    MapDestination,
    MapLayerOut,
    Message,
    SuggestionCreate,
    SuggestionOut,
)
from ..security import hash_session_id
from ..services.geo import haversine_km

router = APIRouter(prefix="/api/tourism", tags=["Tourism"])

SORT_OPTIONS = {"name", "featured", "newest", "district"}


def _base_query(db: Session):
    return select(TourismDestination)


def _apply_filters(
    statement,
    q: str | None,
    categories: list[str] | None,
    district: str | None,
    city: str | None,
    featured: bool | None,
    accessible: bool | None,
    facility: str | None,
    has_coordinates: bool | None,
):
    if q:
        term = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                TourismDestination.name.ilike(term),
                TourismDestination.city.ilike(term),
                TourismDestination.district.ilike(term),
                TourismDestination.locality.ilike(term),
                TourismDestination.description.ilike(term),
                TourismDestination.tags.ilike(term),
                TourismDestination.destination_type.ilike(term),
            )
        )
    if categories:
        statement = statement.where(TourismDestination.category.in_(categories))
    if district:
        statement = statement.where(TourismDestination.district == district)
    if city:
        statement = statement.where(TourismDestination.city.ilike(f"%{city}%"))
    if featured is not None:
        statement = statement.where(TourismDestination.featured == featured)
    if accessible:
        statement = statement.where(
            TourismDestination.accessibility_information.is_not(None),
            TourismDestination.accessibility_information != "",
        )
    if facility:
        statement = statement.where(TourismDestination.facilities.ilike(f"%{facility}%"))
    if has_coordinates is True:
        statement = statement.where(
            TourismDestination.latitude.is_not(None), TourismDestination.longitude.is_not(None)
        )
    elif has_coordinates is False:
        statement = statement.where(
            or_(
                TourismDestination.latitude.is_(None),
                TourismDestination.longitude.is_(None),
            )
        )
    return statement


def _data_gaps(dest: TourismDestination) -> list[str]:
    gaps: list[str] = []
    checks = {
        "visiting_hours": "Visiting hours",
        "entry_fee": "Entry fee",
        "official_website": "Official website",
        "accessibility_information": "Accessibility information",
        "image_reference": "Reusable photograph",
        "contact_information": "Contact details",
        "facilities": "Visitor facilities",
    }
    for field, label in checks.items():
        if not getattr(dest, field):
            gaps.append(label)
    return gaps


def _nearby(
    db: Session, dest: TourismDestination, limit: int = 6, radius_km: float = 40.0
) -> list[DestinationNearby]:
    if dest.latitude is None or dest.longitude is None:
        statement = (
            select(TourismDestination)
            .where(
                TourismDestination.district == dest.district,
                TourismDestination.id != dest.id,
            )
            .order_by(TourismDestination.featured.desc(), TourismDestination.name)
            .limit(limit)
        )
        return [
            DestinationNearby(
                id=item.id,
                name=item.name,
                slug=item.slug,
                category=item.category,
                city=item.city,
                district=item.district,
                latitude=item.latitude,
                longitude=item.longitude,
                distance_km=None,
            )
            for item in db.scalars(statement)
        ]

    # Bounding box pre-filter, then exact haversine.
    lat_delta = radius_km / 111.0
    lon_delta = radius_km / max(1.0, 111.0 * math.cos(math.radians(dest.latitude)))
    candidates = db.scalars(
        select(TourismDestination).where(
            TourismDestination.id != dest.id,
            TourismDestination.latitude.is_not(None),
            TourismDestination.longitude.is_not(None),
            TourismDestination.latitude.between(dest.latitude - lat_delta, dest.latitude + lat_delta),
            TourismDestination.longitude.between(
                dest.longitude - lon_delta, dest.longitude + lon_delta
            ),
        )
    ).all()
    scored = []
    for item in candidates:
        distance = haversine_km(dest.latitude, dest.longitude, item.latitude, item.longitude)
        if distance <= radius_km:
            scored.append((distance, item))
    scored.sort(key=lambda pair: pair[0])
    return [
        DestinationNearby(
            id=item.id,
            name=item.name,
            slug=item.slug,
            category=item.category,
            city=item.city,
            district=item.district,
            latitude=item.latitude,
            longitude=item.longitude,
            distance_km=round(distance, 2),
        )
        for distance, item in scored[:limit]
    ]


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Annotated[Session, Depends(get_db)]):
    counts = dict(
        db.execute(
            select(TourismDestination.category, func.count(TourismDestination.id)).group_by(
                TourismDestination.category
            )
        ).all()
    )
    return [
        CategoryOut(**category, count=int(counts.get(category["slug"], 0)))
        for category in TOURISM_CATEGORIES
    ]


@router.get("/districts", response_model=list[DistrictOut])
def list_districts(db: Annotated[Session, Depends(get_db)]):
    rows = db.execute(
        select(TourismDestination.district, func.count(TourismDestination.id))
        .where(TourismDestination.district.is_not(None))
        .group_by(TourismDestination.district)
        .order_by(TourismDestination.district)
    ).all()
    return [DistrictOut(name=name, count=int(count)) for name, count in rows]


@router.get("/destinations", response_model=DestinationListOut)
def list_destinations(
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[str | None, Query(max_length=120, description="Name, city, district or keyword")] = None,
    category: Annotated[list[str] | None, Query(description="Repeat for multiple categories")] = None,
    district: Annotated[str | None, Query(max_length=120)] = None,
    city: Annotated[str | None, Query(max_length=120)] = None,
    featured: bool | None = None,
    accessible: bool | None = None,
    facility: Annotated[str | None, Query(max_length=40)] = None,
    has_coordinates: bool | None = None,
    sort: Literal["name", "featured", "newest", "district"] = "featured",
    page: Annotated[int, Query(ge=1, le=1000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 12,
):
    categories = [item for item in (category or []) if item]
    unknown = [item for item in categories if item not in CATEGORY_BY_SLUG]
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown category: {', '.join(unknown)}",
        )

    statement = _apply_filters(
        _base_query(db), q, categories, district, city, featured, accessible, facility,
        has_coordinates,
    )
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0

    order = {
        "name": (TourismDestination.name.asc(),),
        "district": (TourismDestination.district.asc(), TourismDestination.name.asc()),
        "newest": (TourismDestination.created_at.desc(),),
        "featured": (
            TourismDestination.featured.desc(),
            TourismDestination.verification_status.desc(),
            TourismDestination.name.asc(),
        ),
    }[sort]
    items = db.scalars(
        statement.order_by(*order).offset((page - 1) * page_size).limit(page_size)
    ).all()

    return DestinationListOut(
        items=[DestinationBase.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        has_more=page * page_size < total,
        filters_applied={
            "q": q,
            "categories": categories,
            "district": district,
            "city": city,
            "featured": featured,
            "accessible": accessible,
            "facility": facility,
            "sort": sort,
        },
    )


@router.get("/destinations/{identifier}", response_model=DestinationOut)
def destination_detail(
    identifier: str,
    db: Annotated[Session, Depends(get_db)],
    nearby_limit: Annotated[int, Query(ge=0, le=20)] = 6,
):
    if identifier.isdigit():
        dest = db.get(TourismDestination, int(identifier))
    else:
        dest = db.scalar(select(TourismDestination).where(TourismDestination.slug == identifier))
    if not dest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Destination not found. It may have been removed or the link is incorrect.",
        )
    payload = DestinationBase.model_validate(dest).model_dump()
    payload["nearby"] = (
        [item.model_dump() for item in _nearby(db, dest, limit=nearby_limit)]
        if nearby_limit
        else []
    )
    payload["data_gaps"] = _data_gaps(dest)
    return DestinationOut(**payload)


@router.get("/nearby", response_model=list[DestinationNearby])
def nearby_destinations(
    db: Annotated[Session, Depends(get_db)],
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    radius_km: Annotated[float, Query(gt=0, le=200)] = 25,
    limit: Annotated[int, Query(ge=1, le=50)] = 12,
    category: Annotated[list[str] | None, Query()] = None,
):
    lat_delta = radius_km / 111.0
    lon_delta = radius_km / max(1.0, 111.0 * math.cos(math.radians(lat)))
    statement = select(TourismDestination).where(
        TourismDestination.latitude.is_not(None),
        TourismDestination.longitude.is_not(None),
        TourismDestination.latitude.between(lat - lat_delta, lat + lat_delta),
        TourismDestination.longitude.between(lon - lon_delta, lon + lon_delta),
    )
    if category:
        statement = statement.where(TourismDestination.category.in_(category))
    results = []
    for item in db.scalars(statement):
        distance = haversine_km(lat, lon, item.latitude, item.longitude)
        if distance <= radius_km:
            results.append((distance, item))
    results.sort(key=lambda pair: pair[0])
    return [
        DestinationNearby(
            id=item.id,
            name=item.name,
            slug=item.slug,
            category=item.category,
            city=item.city,
            district=item.district,
            latitude=item.latitude,
            longitude=item.longitude,
            distance_km=round(distance, 2),
        )
        for distance, item in results[:limit]
    ]


@router.get("/map", response_model=MapLayerOut)
def tourism_map(
    db: Annotated[Session, Depends(get_db)],
    category: Annotated[list[str] | None, Query()] = None,
    district: str | None = None,
    featured: bool | None = None,
):
    statement = select(TourismDestination).where(
        TourismDestination.latitude.is_not(None),
        TourismDestination.longitude.is_not(None),
    )
    if category:
        statement = statement.where(TourismDestination.category.in_(category))
    if district:
        statement = statement.where(TourismDestination.district == district)
    if featured is not None:
        statement = statement.where(TourismDestination.featured == featured)
    rows = db.scalars(statement.order_by(TourismDestination.name)).all()
    markers = [
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
        for item in rows
    ]
    bounds = None
    if markers:
        bounds = {
            "min_lat": min(m.latitude for m in markers),
            "max_lat": max(m.latitude for m in markers),
            "min_lon": min(m.longitude for m in markers),
            "max_lon": max(m.longitude for m in markers),
        }
    return MapLayerOut(
        destinations=markers,
        observations=[],
        bounds=bounds,
        notes=(
            f"{len(markers)} destinations with coordinates are shown. Coordinates "
            "were checked against OpenStreetMap/Photon; records without coordinates "
            "still have detail pages."
        ),
    )


@router.get("/collections")
def collections(db: Annotated[Session, Depends(get_db)]):
    """Curated regional groupings computed from verified records (no fake lists)."""
    groups = [
        {
            "slug": "ekamra-heritage",
            "title": "Ekamra heritage walk",
            "blurb": "Bhubaneswar's Old Town temple cluster and nearby cave sites.",
            "districts": ["Khordha"],
            "categories": ["temple", "monument"],
        },
        {
            "slug": "coastal-odisha",
            "title": "Coastal Odisha",
            "blurb": "Beaches, the Chilika lagoon and coastal wildlife.",
            "districts": ["Puri", "Ganjam", "Balasore", "Kendrapara"],
            "categories": ["beach", "waterfall_lake", "wildlife"],
        },
        {
            "slug": "buddhist-circuit",
            "title": "Buddhist circuit",
            "blurb": "Stupas and monastic sites of the Birupa valley and Dhauli.",
            "districts": ["Jajpur", "Khordha"],
            "categories": ["buddhist", "monument"],
        },
    ]
    output = []
    for group in groups:
        rows = db.scalars(
            select(TourismDestination)
            .where(
                TourismDestination.district.in_(group["districts"]),
                TourismDestination.category.in_(group["categories"]),
            )
            .order_by(TourismDestination.featured.desc(), TourismDestination.name)
            .limit(6)
        ).all()
        output.append(
            {
                "slug": group["slug"],
                "title": group["title"],
                "blurb": group["blurb"],
                "places": [DestinationBase.model_validate(item).model_dump() for item in rows],
            }
        )
    return output


@router.post("/suggestions", response_model=SuggestionOut, status_code=201)
def suggest_destination(
    payload: SuggestionCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    write_limiter.check(client_key(request, "suggestion"))
    if not payload.consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consent is required so reviewers may follow up on this suggestion.",
        )
    if payload.category not in CATEGORY_BY_SLUG:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown category '{payload.category}'.",
        )
    report = ReviewReport(
        record_type="destination",
        record_id=None,
        record_label=payload.name,
        report_reason="missing_place",
        report_details=(
            f"Category: {payload.category}\n"
            f"District: {payload.district or 'unknown'}\n"
            f"City: {payload.city or 'unknown'}\n"
            f"Source: {payload.source_url or 'not supplied'}\n"
            f"Description: {payload.description or 'not supplied'}\n"
            f"Contact: {payload.submitter_contact or 'not supplied'}"
        ),
        status="open",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return SuggestionOut(
        id=report.id,
        status=report.status,
        message=(
            "Thank you. Your suggestion is queued for review. It will not appear "
            "publicly until a reviewer verifies the source and details."
        ),
    )


@router.post("/corrections", response_model=Message, status_code=201)
def submit_correction(
    payload: CorrectionCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    x_session_id: Annotated[str | None, Header()] = None,
):
    write_limiter.check(client_key(request, "correction"))
    dest = db.get(TourismDestination, payload.destination_id)
    if not dest:
        raise HTTPException(status_code=404, detail="Destination not found.")
    db.add(
        ReviewReport(
            record_type="destination",
            record_id=dest.id,
            record_label=dest.name,
            report_reason=f"correction:{payload.field_name}",
            report_details=(
                f"Current value: {payload.current_value or 'blank'}\n"
                f"Suggested value: {payload.suggested_value}\n"
                f"Explanation: {payload.explanation or 'not supplied'}\n"
                f"Source: {payload.source_url or 'not supplied'}"
            ),
            status="open",
            session_hash=hash_session_id(x_session_id),
        )
    )
    db.commit()
    return Message(
        message="Correction submitted for review.",
        detail="Tourism details are only changed after a reviewer checks the source you provided.",
    )
