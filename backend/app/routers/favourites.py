"""Favourites (saved places) scoped to an anonymous browser session."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Favourite, TourismDestination
from ..schemas import DestinationBase, FavouriteOut
from ..security import require_session_id

router = APIRouter(prefix="/api/favourites", tags=["Favourites"])


@router.get("", response_model=list[FavouriteOut])
def list_favourites(
    db: Annotated[Session, Depends(get_db)],
    session_hash: Annotated[str, Depends(require_session_id)],
):
    rows = db.scalars(
        select(Favourite)
        .where(Favourite.session_hash == session_hash)
        .order_by(Favourite.created_at.desc())
    ).all()
    return [
        FavouriteOut(
            id=row.id,
            destination=DestinationBase.model_validate(row.destination),
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/{destination_id}", response_model=FavouriteOut, status_code=201)
def add_favourite(
    destination_id: int,
    db: Annotated[Session, Depends(get_db)],
    session_hash: Annotated[str, Depends(require_session_id)],
):
    destination = db.get(TourismDestination, destination_id)
    if not destination:
        raise HTTPException(status_code=404, detail="Destination not found.")
    existing = db.scalar(
        select(Favourite).where(
            Favourite.session_hash == session_hash,
            Favourite.destination_id == destination_id,
        )
    )
    if existing:
        return FavouriteOut(
            id=existing.id,
            destination=DestinationBase.model_validate(destination),
            created_at=existing.created_at,
        )
    favourite = Favourite(session_hash=session_hash, destination_id=destination_id)
    db.add(favourite)
    db.commit()
    db.refresh(favourite)
    return FavouriteOut(
        id=favourite.id,
        destination=DestinationBase.model_validate(destination),
        created_at=favourite.created_at,
    )


@router.delete("/{destination_id}", status_code=204)
def remove_favourite(
    destination_id: int,
    db: Annotated[Session, Depends(get_db)],
    session_hash: Annotated[str, Depends(require_session_id)],
):
    favourite = db.scalar(
        select(Favourite).where(
            Favourite.session_hash == session_hash,
            Favourite.destination_id == destination_id,
        )
    )
    if not favourite:
        raise HTTPException(status_code=404, detail="This place is not in your saved list.")
    db.delete(favourite)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
