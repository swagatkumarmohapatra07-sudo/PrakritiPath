"""Personal travel planner: itineraries with ordered stops."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import Itinerary, ItineraryStop, TourismDestination
from ..schemas import (
    DestinationBase,
    ItineraryCreate,
    ItineraryOut,
    ItineraryStopOut,
    ItineraryUpdate,
)
from ..security import require_session_id

router = APIRouter(prefix="/api/itineraries", tags=["Travel planner"])

TRIP_DISCLAIMER = (
    "Opening hours, entry fees and travel times can change. This plan does not "
    "provide live traffic, route optimisation or guaranteed opening times; verify "
    "with the destination before travelling."
)


def _load(db: Session, itinerary_id: int, session_hash: str) -> Itinerary:
    itinerary = db.scalar(
        select(Itinerary)
        .options(
            selectinload(Itinerary.stops).selectinload(ItineraryStop.destination)
        )
        .where(Itinerary.id == itinerary_id, Itinerary.session_hash == session_hash)
    )
    if not itinerary:
        raise HTTPException(
            status_code=404,
            detail="Itinerary not found. It may belong to a different browser session.",
        )
    return itinerary


def _serialize(itinerary: Itinerary) -> ItineraryOut:
    stops = []
    total = 0
    missing_estimate = False
    for stop in sorted(itinerary.stops, key=lambda item: item.stop_order):
        stops.append(
            ItineraryStopOut(
                id=stop.id,
                stop_order=stop.stop_order,
                notes=stop.notes,
                destination=DestinationBase.model_validate(stop.destination),
            )
        )
        if stop.destination.estimated_visit_minutes:
            total += stop.destination.estimated_visit_minutes
        else:
            missing_estimate = True
    return ItineraryOut(
        id=itinerary.id,
        title=itinerary.title,
        travel_date=itinerary.travel_date,
        notes=itinerary.notes,
        created_at=itinerary.created_at,
        stops=stops,
        total_estimated_minutes=total if not missing_estimate else None,
        disclaimer=TRIP_DISCLAIMER,
    )


def _apply_stops(db: Session, itinerary: Itinerary, stops: list) -> None:
    destination_ids = [stop.destination_id for stop in stops]
    if len(set(destination_ids)) != len(destination_ids):
        raise HTTPException(
            status_code=422,
            detail="A destination can only appear once in an itinerary. Edit the stop instead.",
        )
    found = db.scalars(
        select(TourismDestination).where(TourismDestination.id.in_(destination_ids))
    ).all() if destination_ids else []
    if len(found) != len(destination_ids):
        missing = sorted(set(destination_ids) - {item.id for item in found})
        raise HTTPException(
            status_code=422,
            detail=f"Unknown destination id(s): {missing}",
        )

    itinerary.stops.clear()
    db.flush()
    for order, stop in enumerate(stops):
        itinerary.stops.append(
            ItineraryStop(
                destination_id=stop.destination_id,
                stop_order=order,
                notes=stop.notes,
            )
        )


@router.get("", response_model=list[ItineraryOut])
def list_itineraries(
    db: Annotated[Session, Depends(get_db)],
    session_hash: Annotated[str, Depends(require_session_id)],
):
    rows = db.scalars(
        select(Itinerary)
        .options(selectinload(Itinerary.stops).selectinload(ItineraryStop.destination))
        .where(Itinerary.session_hash == session_hash)
        .order_by(Itinerary.created_at.desc())
    ).all()
    return [_serialize(row) for row in rows]


@router.post("", response_model=ItineraryOut, status_code=201)
def create_itinerary(
    payload: ItineraryCreate,
    db: Annotated[Session, Depends(get_db)],
    session_hash: Annotated[str, Depends(require_session_id)],
):
    if payload.travel_date and payload.travel_date < date(2000, 1, 1):
        raise HTTPException(status_code=422, detail="Travel date is not plausible.")
    itinerary = Itinerary(
        session_hash=session_hash,
        title=payload.title.strip(),
        travel_date=payload.travel_date,
        notes=payload.notes,
    )
    db.add(itinerary)
    db.flush()
    _apply_stops(db, itinerary, payload.stops)
    db.commit()
    return _serialize(_load(db, itinerary.id, session_hash))


@router.get("/{itinerary_id}", response_model=ItineraryOut)
def get_itinerary(
    itinerary_id: int,
    db: Annotated[Session, Depends(get_db)],
    session_hash: Annotated[str, Depends(require_session_id)],
):
    return _serialize(_load(db, itinerary_id, session_hash))


@router.put("/{itinerary_id}", response_model=ItineraryOut)
def update_itinerary(
    itinerary_id: int,
    payload: ItineraryUpdate,
    db: Annotated[Session, Depends(get_db)],
    session_hash: Annotated[str, Depends(require_session_id)],
):
    itinerary = _load(db, itinerary_id, session_hash)
    if payload.title is not None:
        itinerary.title = payload.title.strip()
    if payload.travel_date is not None:
        itinerary.travel_date = payload.travel_date
    if payload.notes is not None:
        itinerary.notes = payload.notes
    if payload.stops is not None:
        _apply_stops(db, itinerary, payload.stops)
    db.commit()
    return _serialize(_load(db, itinerary.id, session_hash))


@router.delete("/{itinerary_id}", status_code=204)
def delete_itinerary(
    itinerary_id: int,
    db: Annotated[Session, Depends(get_db)],
    session_hash: Annotated[str, Depends(require_session_id)],
):
    itinerary = _load(db, itinerary_id, session_hash)
    db.delete(itinerary)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
