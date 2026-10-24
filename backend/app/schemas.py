"""Pydantic request/response schemas (API contract).

Kept separate from ORM models so the public API can hide internal fields such
as session hashes and uploaded file system paths.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Category = Literal["plant", "bird"]
VerificationStatus = Literal["pending", "verified", "rejected", "needs_review"]


# --------------------------------------------------------------------------- #
# Shared
# --------------------------------------------------------------------------- #
class Message(BaseModel):
    message: str
    detail: str | None = None


class StatsOut(BaseModel):
    destinations_total: int
    destinations_verified: int
    districts_covered: int
    categories_covered: int
    observations_total: int
    observations_verified: int
    species_catalogued: int
    plant_species: int
    bird_species: int
    model_available: bool
    generated_at: datetime
    notes: str = (
        "Counts are computed live from the database; no figures are hardcoded."
    )


# --------------------------------------------------------------------------- #
# Tourism
# --------------------------------------------------------------------------- #
class CategoryOut(BaseModel):
    slug: str
    label: str
    group: str
    icon: str
    description: str
    count: int = 0


class DistrictOut(BaseModel):
    name: str
    count: int


class DestinationBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    category: str
    destination_type: str | None = None
    description: str | None = None
    significance: str | None = None
    address: str | None = None
    locality: str | None = None
    city: str | None = None
    district: str | None = None
    state: str = "Odisha"
    latitude: float | None = None
    longitude: float | None = None
    visiting_hours: str | None = None
    closed_days: str | None = None
    entry_fee: str | None = None
    estimated_visit_minutes: int | None = None
    facilities: list[str] = Field(default_factory=list)
    accessibility_information: str | None = None
    photography_policy: str | None = None
    dress_code: str | None = None
    visitor_guidelines: str | None = None
    official_website: str | None = None
    contact_information: str | None = None
    image_reference: str | None = None
    image_credit: str | None = None
    image_licence: str | None = None
    # Cover photograph resolved from the destination_images table.
    cover_image: str | None = None
    cover_image_thumbnail: str | None = None
    cover_image_credit: str | None = None
    cover_image_licence: str | None = None
    source_url: str | None = None
    source_name: str | None = None
    licence_information: str | None = None
    last_verified_at: date | None = None
    verification_status: str = "provisional"
    featured: bool = False
    tags: list[str] = Field(default_factory=list)

    @field_validator("facilities", mode="before")
    @classmethod
    def _parse_facilities(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return [str(item) for item in parsed] if isinstance(parsed, list) else []
            except json.JSONDecodeError:
                return [part.strip() for part in value.split(",") if part.strip()]
        return list(value)

    @field_validator("tags", mode="before")
    @classmethod
    def _parse_tags(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return list(value)


class DestinationImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    url: str
    thumbnail_url: str | None = None
    page_url: str
    title: str | None = None
    credit: str | None = None
    licence: str | None = None
    licence_url: str | None = None
    width: int | None = None
    height: int | None = None
    source_name: str = "Wikimedia Commons"


class DestinationOut(DestinationBase):
    nearby: list["DestinationNearby"] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    images: list[DestinationImageOut] = Field(default_factory=list)


class DestinationNearby(BaseModel):
    id: int
    name: str
    slug: str
    category: str
    city: str | None = None
    district: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    distance_km: float | None = None


class DestinationListOut(BaseModel):
    items: list[DestinationBase]
    total: int
    page: int
    page_size: int
    has_more: bool
    filters_applied: dict[str, Any] = Field(default_factory=dict)


class MapDestination(BaseModel):
    id: int
    name: str
    slug: str
    category: str
    district: str | None = None
    city: str | None = None
    latitude: float
    longitude: float
    featured: bool = False
    verification_status: str


class MapObservation(BaseModel):
    id: int
    label: str
    category: str
    verification_status: str
    latitude: float
    longitude: float
    location_precision: str
    created_at: datetime
    obscured: bool


class MapLayerOut(BaseModel):
    destinations: list[MapDestination]
    observations: list[MapObservation]
    bounds: dict[str, float] | None = None
    notes: str


class SuggestionCreate(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    category: str = Field(min_length=2, max_length=40)
    district: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    source_url: str | None = Field(default=None, max_length=500)
    submitter_contact: str | None = Field(default=None, max_length=200)
    consent: bool = True


class SuggestionOut(BaseModel):
    id: int
    status: str
    message: str


class CorrectionCreate(BaseModel):
    destination_id: int
    field_name: str = Field(min_length=2, max_length=60)
    current_value: str | None = Field(default=None, max_length=500)
    suggested_value: str = Field(min_length=2, max_length=1000)
    explanation: str | None = Field(default=None, max_length=1000)
    source_url: str | None = Field(default=None, max_length=500)


# --------------------------------------------------------------------------- #
# Biodiversity
# --------------------------------------------------------------------------- #
class QualityOut(BaseModel):
    status: Literal["good", "warning", "poor"]
    usable: bool
    width: int | None = None
    height: int | None = None
    brightness: float | None = None
    sharpness: float | None = None
    issues: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PredictionClass(BaseModel):
    scientific_name: str
    common_name: str
    confidence: float
    species_id: int | None = None
    rank: int


class LocationCheckOut(BaseModel):
    status: Literal["plausible", "outside_known_range", "unavailable", "not_provided"]
    message: str
    district: str | None = None
    region_code: str | None = None


class PredictionOut(BaseModel):
    model_available: bool
    model_version: str | None = None
    category: Category
    quality: QualityOut
    top_predictions: list[PredictionClass] = Field(default_factory=list)
    confidence: float | None = None
    confidence_label: str | None = None
    abstain: bool = True
    decision: Literal["accept", "review", "reject", "unavailable"]
    abstain_reason: str | None = None
    location_check: LocationCheckOut
    threshold: float | None = None
    explanation: str
    limitations: list[str] = Field(default_factory=list)
    disclaimer: str
    model_card: dict[str, Any] | None = None


class ModelStatusOut(BaseModel):
    plant: dict[str, Any]
    bird: dict[str, Any]
    torch_installed: bool


class SpeciesImageOut(BaseModel):
    url: str
    thumbnail_url: str | None = None
    page_url: str
    title: str | None = None
    credit: str | None = None
    licence: str | None = None
    licence_url: str | None = None
    source_name: str = "Wikimedia Commons"


class SpeciesSourceOut(BaseModel):
    label: str
    url: str
    kind: str = "reference"
    note: str | None = None


class SpeciesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    common_name: str
    scientific_name: str
    category: str
    description: str | None = None
    habitat: str | None = None
    distribution_information: str | None = None
    conservation_status: str | None = None
    source: str | None = None
    licence_information: str | None = None
    image_url: str | None = None
    image_credit: str | None = None
    images: list[SpeciesImageOut] = Field(default_factory=list)
    sources: list[SpeciesSourceOut] = Field(default_factory=list)
    odisha_note: str | None = None


class ObservationOut(BaseModel):
    id: int
    category: str
    predicted_species: str
    predicted_common_name: str | None = None
    species_id: int | None = None
    species: SpeciesOut | None = None
    confidence_score: float
    image_url: str
    image_quality_status: str
    latitude: float | None = None
    longitude: float | None = None
    location_precision: str
    district: str | None = None
    observer_notes: str | None = None
    verification_status: str
    review_notes: str | None = None
    consented: bool
    data_source: str
    model_version: str | None = None
    created_at: datetime
    can_delete: bool = False
    location_note: str | None = None


class ObservationListOut(BaseModel):
    items: list[ObservationOut]
    total: int
    page: int
    page_size: int


class ObservationSubmit(BaseModel):
    """Metadata that accompanies a consenting observation submission.

    The image and prediction are produced by /predict; the client must upload
    them back or reference the prediction token. To keep the flow simple for
    beginners, the app re-sends the image with this metadata.
    """

    predicted_species: str = Field(min_length=2, max_length=160)
    predicted_common_name: str | None = Field(default=None, max_length=160)
    category: Category
    confidence_score: float = Field(ge=0, le=1)
    top_predictions: list[dict[str, Any]] = Field(default_factory=list)
    image_quality_status: str = Field(default="unknown", max_length=32)
    image_quality_notes: str | None = Field(default=None, max_length=1000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_precision: Literal["exact", "approximate", "district", "none"] = "none"
    district: str | None = Field(default=None, max_length=120)
    observer_notes: str | None = Field(default=None, max_length=2000)
    consent: bool
    model_version: str | None = Field(default=None, max_length=80)
    data_source: str = Field(default="user_upload", max_length=64)


class ReportCreate(BaseModel):
    record_type: Literal["observation", "destination", "species", "prediction"]
    record_id: int | None = None
    record_label: str | None = Field(default=None, max_length=220)
    report_reason: str = Field(min_length=3, max_length=80)
    report_details: str | None = Field(default=None, max_length=2000)


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    record_type: str
    record_id: int | None
    status: str
    created_at: datetime


# --------------------------------------------------------------------------- #
# Favourites / itineraries
# --------------------------------------------------------------------------- #
class FavouriteOut(BaseModel):
    id: int
    destination: DestinationBase
    created_at: datetime


class ItineraryStopIn(BaseModel):
    destination_id: int
    notes: str | None = Field(default=None, max_length=1000)


class ItineraryCreate(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    travel_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)
    stops: list[ItineraryStopIn] = Field(default_factory=list, max_length=30)


class ItineraryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=160)
    travel_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)
    stops: list[ItineraryStopIn] | None = Field(default=None, max_length=30)


class ItineraryStopOut(BaseModel):
    id: int
    stop_order: int
    notes: str | None
    destination: DestinationBase


class ItineraryOut(BaseModel):
    id: int
    title: str
    travel_date: date | None
    notes: str | None
    created_at: datetime
    stops: list[ItineraryStopOut]
    total_estimated_minutes: int | None = None
    disclaimer: str = (
        "Opening hours, entry fees and travel times can change. Verify before you travel."
    )


# --------------------------------------------------------------------------- #
# Admin
# --------------------------------------------------------------------------- #
class AdminLogin(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=6, max_length=200)


class AdminToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    username: str


class AdminOverview(BaseModel):
    pending_observations: int
    open_reports: int
    unverified_destinations: int
    total_observations: int
    total_destinations: int
    recent_reports: list[dict[str, Any]]
    recent_observations: list[dict[str, Any]]


class ObservationReview(BaseModel):
    verification_status: VerificationStatus
    review_notes: str | None = Field(default=None, max_length=1000)
    species_id: int | None = None
    sensitive: bool | None = None


class DestinationReview(BaseModel):
    verification_status: Literal["provisional", "verified", "needs_review", "rejected"]
    note: str | None = Field(default=None, max_length=1000)


class ReportUpdate(BaseModel):
    status: Literal["open", "in_review", "resolved", "dismissed"]


# Fix forward reference for the nested nearby list.
DestinationOut.model_rebuild()
