"""Public correction / problem reports and review queue intake."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import BiodiversityObservation, ReviewReport, TourismDestination
from ..rate_limit import client_key, write_limiter
from ..schemas import ReportCreate, ReportOut
from ..security import hash_session_id

router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.post("", response_model=ReportOut, status_code=201)
def create_report(
    payload: ReportCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    x_session_id: Annotated[str | None, Header()] = None,
):
    write_limiter.check(client_key(request, "report"))

    if payload.record_type == "observation" and payload.record_id is not None:
        if not db.get(BiodiversityObservation, payload.record_id):
            raise HTTPException(status_code=404, detail="Observation not found.")
    if payload.record_type == "destination" and payload.record_id is not None:
        if not db.get(TourismDestination, payload.record_id):
            raise HTTPException(status_code=404, detail="Destination not found.")

    report = ReviewReport(
        record_type=payload.record_type,
        record_id=payload.record_id,
        record_label=payload.record_label,
        report_reason=payload.report_reason.strip(),
        report_details=payload.report_details,
        status="open",
        session_hash=hash_session_id(x_session_id),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return ReportOut.model_validate(report)


@router.get("/mine", response_model=list[ReportOut])
def my_reports(
    db: Annotated[Session, Depends(get_db)],
    x_session_id: Annotated[str | None, Header()] = None,
):
    session_hash = hash_session_id(x_session_id)
    if not session_hash:
        raise HTTPException(status_code=400, detail="Missing X-Session-Id header.")
    rows = db.scalars(
        select(ReviewReport)
        .where(ReviewReport.session_hash == session_hash)
        .order_by(ReviewReport.created_at.desc())
    ).all()
    return [ReportOut.model_validate(row) for row in rows]
