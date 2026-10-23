"""SQLAlchemy ORM models for BioTrace.

Design notes
------------
* Anonymous visitors get a random session id (stored in localStorage). It is
  hashed before being written to the database so itineraries/favourites can be
  scoped without collecting personal data.
* Biodiversity coordinates are optional. Sensitive records are stored with a
  precision flag and served with reduced precision by the public API.
* Tourism records never invent timings, prices or contact details: unknown
  fields are SQL NULL and the UI renders "Not verified".
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return uuid.uuid4().hex


class Species(Base):
    __tablename__ = "species"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    common_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    scientific_name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # plant | bird
    description: Mapped[str | None] = mapped_column(Text)
    habitat: Mapped[str | None] = mapped_column(Text)
    distribution_information: Mapped[str | None] = mapped_column(Text)
    # ISO-3166-2-ish or free-text regions where the species is recorded. Used
    # only as a soft plausibility signal, never proof of absence.
    known_regions: Mapped[str | None] = mapped_column(Text)  # e.g. "IN-OR,IN-WB"
    conservation_status: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str | None] = mapped_column(Text)
    licence_information: Mapped[str | None] = mapped_column(String(255))
    image_url: Mapped[str | None] = mapped_column(Text)
    image_credit: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    observations: Mapped[list["BiodiversityObservation"]] = relationship(back_populates="species")

    __table_args__ = (
        CheckConstraint("category IN ('plant','bird')", name="ck_species_category"),
        Index("ix_species_category_common", "category", "common_name"),
    )


class BiodiversityObservation(Base):
    __tablename__ = "biodiversity_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    species_id: Mapped[int | None] = mapped_column(ForeignKey("species.id"), nullable=True)
    predicted_species: Mapped[str] = mapped_column(String(160), nullable=False)
    predicted_common_name: Mapped[str | None] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(16), nullable=False, default="plant")
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    top_predictions_json: Mapped[str | None] = mapped_column(Text)
    image_path: Mapped[str] = mapped_column(Text, nullable=False)
    image_quality_status: Mapped[str] = mapped_column(String(32), default="unknown")
    image_quality_notes: Mapped[str | None] = mapped_column(Text)

    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    location_precision: Mapped[str] = mapped_column(String(24), default="unknown")
    district: Mapped[str | None] = mapped_column(String(120), index=True)

    observer_notes: Mapped[str | None] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    review_notes: Mapped[str | None] = mapped_column(Text)
    consented: Mapped[bool] = mapped_column(Boolean, default=False)
    data_source: Mapped[str] = mapped_column(String(64), default="user_upload")
    model_version: Mapped[str | None] = mapped_column(String(80))
    derived_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_session_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    species: Mapped[Species | None] = relationship(back_populates="observations")

    __table_args__ = (
        CheckConstraint("category IN ('plant','bird')", name="ck_obs_category"),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="ck_obs_conf"),
        CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)", name="ck_obs_lat"
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)", name="ck_obs_lon"
        ),
        CheckConstraint(
            "location_precision IN ('exact','approximate','district','none','unknown')",
            name="ck_obs_precision",
        ),
        Index("ix_obs_status_created", "verification_status", "created_at"),
    )


class TourismDestination(Base):
    __tablename__ = "tourism_destinations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(220), nullable=False, unique=True, index=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    destination_type: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)
    significance: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    locality: Mapped[str | None] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(120), index=True)
    district: Mapped[str | None] = mapped_column(String(120), index=True)
    state: Mapped[str] = mapped_column(String(80), default="Odisha")
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    visiting_hours: Mapped[str | None] = mapped_column(String(255))
    closed_days: Mapped[str | None] = mapped_column(String(255))
    entry_fee: Mapped[str | None] = mapped_column(String(255))
    estimated_visit_minutes: Mapped[int | None] = mapped_column(Integer)
    facilities: Mapped[str | None] = mapped_column(Text)  # JSON array encoded as text
    accessibility_information: Mapped[str | None] = mapped_column(Text)
    photography_policy: Mapped[str | None] = mapped_column(Text)
    dress_code: Mapped[str | None] = mapped_column(Text)
    visitor_guidelines: Mapped[str | None] = mapped_column(Text)
    official_website: Mapped[str | None] = mapped_column(Text)
    contact_information: Mapped[str | None] = mapped_column(String(255))

    image_reference: Mapped[str | None] = mapped_column(Text)
    image_credit: Mapped[str | None] = mapped_column(Text)
    image_licence: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(Text)
    source_name: Mapped[str | None] = mapped_column(String(160))
    licence_information: Mapped[str | None] = mapped_column(String(255))
    last_verified_at: Mapped[date | None] = mapped_column(Date)
    verification_status: Mapped[str] = mapped_column(String(24), default="provisional", index=True)
    featured: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    tags: Mapped[str | None] = mapped_column(String(255))
    osm_id: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)", name="ck_dest_lat"
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)", name="ck_dest_lon"
        ),
        CheckConstraint(
            "verification_status IN ('provisional','verified','needs_review','rejected')",
            name="ck_dest_status",
        ),
        Index("ix_dest_category_district", "category", "district"),
    )


class Favourite(Base):
    __tablename__ = "favourites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    destination_id: Mapped[int] = mapped_column(
        ForeignKey("tourism_destinations.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    destination: Mapped[TourismDestination] = relationship()

    __table_args__ = (
        UniqueConstraint("session_hash", "destination_id", name="uq_fav_session_dest"),
    )


class Itinerary(Base):
    __tablename__ = "itineraries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    travel_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    stops: Mapped[list["ItineraryStop"]] = relationship(
        back_populates="itinerary",
        cascade="all, delete-orphan",
        order_by="ItineraryStop.stop_order",
    )


class ItineraryStop(Base):
    __tablename__ = "itinerary_stops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    itinerary_id: Mapped[int] = mapped_column(
        ForeignKey("itineraries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    destination_id: Mapped[int] = mapped_column(
        ForeignKey("tourism_destinations.id", ondelete="CASCADE"), nullable=False
    )
    stop_order: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    itinerary: Mapped[Itinerary] = relationship(back_populates="stops")
    destination: Mapped[TourismDestination] = relationship()

    __table_args__ = (
        UniqueConstraint("itinerary_id", "stop_order", name="uq_stop_order"),
        CheckConstraint("stop_order >= 0", name="ck_stop_order"),
    )


class ReviewReport(Base):
    __tablename__ = "review_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    record_id: Mapped[int | None] = mapped_column(Integer)
    record_label: Mapped[str | None] = mapped_column(String(220))
    report_reason: Mapped[str] = mapped_column(String(80), nullable=False)
    report_details: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    session_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        CheckConstraint(
            "record_type IN ('observation','destination','species','prediction')",
            name="ck_report_type",
        ),
        CheckConstraint(
            "status IN ('open','in_review','resolved','dismissed')", name="ck_report_status"
        ),
    )


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ImportLog(Base):
    """Audit trail for the tourism import pipeline."""

    __tablename__ = "import_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_file: Mapped[str] = mapped_column(String(255))
    imported: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
