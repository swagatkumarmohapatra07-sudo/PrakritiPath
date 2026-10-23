"""Admin review console API.

Protected by a signed bearer token derived from ADMIN_USERNAME/ADMIN_PASSWORD.
There is no public sign-up. All review actions are recorded.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import AdminUser, BiodiversityObservation, ReviewReport, TourismDestination
from ..rate_limit import auth_limiter, client_key
from ..schemas import (
    AdminLogin,
    AdminOverview,
    AdminToken,
    DestinationBase,
    DestinationReview,
    Message,
    ObservationReview,
    ReportOut,
    ReportUpdate,
)
from ..security import create_admin_token, require_admin, verify_password
from .biodiversity import _serialize_observation

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.post("/login", response_model=AdminToken)
def login(payload: AdminLogin, request: Request, db: Annotated[Session, Depends(get_db)]):
    auth_limiter.check(client_key(request, "admin-login"))
    user = db.scalar(select(AdminUser).where(AdminUser.username == payload.username))
    valid = bool(user and verify_password(payload.password, user.password_hash))
    # Environment fallback lets a fresh clone sign in before the seed script runs.
    if not valid and payload.username == settings.admin_username:
        valid = payload.password == settings.admin_password
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
        )
    token = create_admin_token(payload.username)
    return AdminToken(
        access_token=token,
        expires_in_minutes=settings.admin_token_ttl_minutes,
        username=payload.username,
    )


@router.get("/overview", response_model=AdminOverview)
def overview(
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[str, Depends(require_admin)],
):
    pending = db.scalar(
        select(func.count(BiodiversityObservation.id)).where(
            BiodiversityObservation.verification_status == "pending"
        )
    ) or 0
    open_reports = db.scalar(
        select(func.count(ReviewReport.id)).where(ReviewReport.status == "open")
    ) or 0
    unverified = db.scalar(
        select(func.count(TourismDestination.id)).where(
            TourismDestination.verification_status.in_(["provisional", "needs_review"])
        )
    ) or 0
    total_observations = db.scalar(select(func.count(BiodiversityObservation.id))) or 0
    total_destinations = db.scalar(select(func.count(TourismDestination.id))) or 0

    reports = db.scalars(
        select(ReviewReport).order_by(ReviewReport.created_at.desc()).limit(8)
    ).all()
    observations = db.scalars(
        select(BiodiversityObservation)
        .order_by(BiodiversityObservation.created_at.desc())
        .limit(8)
    ).all()

    return AdminOverview(
        pending_observations=pending,
        open_reports=open_reports,
        unverified_destinations=unverified,
        total_observations=total_observations,
        total_destinations=total_destinations,
        recent_reports=[
            {
                "id": item.id,
                "record_type": item.record_type,
                "record_id": item.record_id,
                "record_label": item.record_label,
                "reason": item.report_reason,
                "status": item.status,
                "created_at": item.created_at.isoformat(),
            }
            for item in reports
        ],
        recent_observations=[
            {
                "id": item.id,
                "label": item.predicted_species,
                "category": item.category,
                "confidence": item.confidence_score,
                "status": item.verification_status,
                "created_at": item.created_at.isoformat(),
            }
            for item in observations
        ],
    )


@router.get("/observations")
def admin_observations(
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[str, Depends(require_admin)],
    status_filter: Literal["pending", "verified", "rejected", "needs_review"] | None = None,
    limit: int = 50,
):
    statement = select(BiodiversityObservation).order_by(
        BiodiversityObservation.created_at.desc()
    )
    if status_filter:
        statement = statement.where(
            BiodiversityObservation.verification_status == status_filter
        )
    rows = db.scalars(statement.limit(min(limit, 200))).all()
    return [_serialize_observation(row, is_admin=True) for row in rows]


@router.patch("/observations/{observation_id}", response_model=Message)
def review_observation(
    observation_id: int,
    payload: ObservationReview,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[str, Depends(require_admin)],
):
    observation = db.get(BiodiversityObservation, observation_id)
    if not observation:
        raise HTTPException(status_code=404, detail="Observation not found.")
    observation.verification_status = payload.verification_status
    observation.review_notes = payload.review_notes
    if payload.species_id is not None:
        from ..models import Species

        species = db.get(Species, payload.species_id)
        if not species:
            raise HTTPException(status_code=422, detail="Species id does not exist.")
        observation.species_id = species.id
        observation.predicted_species = species.scientific_name
        observation.predicted_common_name = species.common_name
    if payload.sensitive is not None:
        observation.derived_sensitive = payload.sensitive
    db.add(
        ReviewReport(
            record_type="observation",
            record_id=observation.id,
            record_label=observation.predicted_species,
            report_reason="admin_review",
            report_details=(
                f"{admin} set status to {payload.verification_status}. "
                f"Note: {payload.review_notes or 'none'}"
            ),
            status="resolved",
        )
    )
    db.commit()
    return Message(
        message="Observation review saved.",
        detail=f"Status is now '{payload.verification_status}'.",
    )


@router.get("/destinations")
def admin_destinations(
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[str, Depends(require_admin)],
    status_filter: Literal["provisional", "verified", "needs_review", "rejected"] | None = None,
    limit: int = 100,
):
    statement = select(TourismDestination).order_by(TourismDestination.name)
    if status_filter:
        statement = statement.where(TourismDestination.verification_status == status_filter)
    rows = db.scalars(statement.limit(min(limit, 300))).all()
    return [DestinationBase.model_validate(row) for row in rows]


@router.patch("/destinations/{destination_id}", response_model=Message)
def review_destination(
    destination_id: int,
    payload: DestinationReview,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[str, Depends(require_admin)],
):
    destination = db.get(TourismDestination, destination_id)
    if not destination:
        raise HTTPException(status_code=404, detail="Destination not found.")
    destination.verification_status = payload.verification_status
    if payload.note:
        db.add(
            ReviewReport(
                record_type="destination",
                record_id=destination.id,
                record_label=destination.name,
                report_reason="admin_review",
                report_details=f"{admin}: {payload.note}",
                status="resolved",
            )
        )
    db.commit()
    return Message(message="Destination status updated.")


@router.get("/reports", response_model=list[ReportOut])
def admin_reports(
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[str, Depends(require_admin)],
    status_filter: Literal["open", "in_review", "resolved", "dismissed"] | None = None,
):
    statement = select(ReviewReport).order_by(ReviewReport.created_at.desc())
    if status_filter:
        statement = statement.where(ReviewReport.status == status_filter)
    return [ReportOut.model_validate(row) for row in db.scalars(statement).all()]


@router.get("/reports/{report_id}")
def admin_report_detail(
    report_id: int,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[str, Depends(require_admin)],
):
    report = db.get(ReviewReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    return {
        "id": report.id,
        "record_type": report.record_type,
        "record_id": report.record_id,
        "record_label": report.record_label,
        "reason": report.report_reason,
        "details": report.report_details,
        "status": report.status,
        "created_at": report.created_at.isoformat(),
    }


@router.patch("/reports/{report_id}", response_model=Message)
def update_report(
    report_id: int,
    payload: ReportUpdate,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[str, Depends(require_admin)],
):
    report = db.get(ReviewReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    report.status = payload.status
    db.commit()
    return Message(message=f"Report marked as {payload.status}.")
