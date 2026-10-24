"""Biodiversity API: trustworthy prediction workflow, observations, species."""

from __future__ import annotations

import json
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import BiodiversityObservation, Species
from ..rate_limit import client_key, upload_limiter
from ..schemas import (
    LocationCheckOut,
    ModelStatusOut,
    ObservationListOut,
    ObservationOut,
    PredictionClass,
    PredictionOut,
    QualityOut,
    SpeciesOut,
)
from ..security import hash_session_id, require_session_id
from ..services import geo, species_media
from ..services.image_quality import ImageValidationError, assess_quality, load_and_validate
from ..services.predictor import DEFAULT_LIMITATIONS, ModelNotAvailable, registry
from ..services.storage import delete_observation_image, image_url, save_observation_image

router = APIRouter(prefix="/api/biodiversity", tags=["Biodiversity"])

DISCLAIMER = (
    "AI predictions are preliminary screening suggestions, not verified biodiversity "
    "records. Confidence is the model's score for its chosen label, not the probability "
    "that the identification is correct. Records are shown as pending until a human "
    "reviews them."
)

CONFIDENCE_LABELS = (
    (0.80, "High for this model — still not a guarantee"),
    (0.55, "Moderate — human review recommended"),
    (0.0, "Low — treat as a guess"),
)


def _confidence_label(confidence: float | None) -> str | None:
    if confidence is None:
        return None
    for cutoff, label in CONFIDENCE_LABELS:
        if confidence >= cutoff:
            return label
    return None


def _species_map(db: Session, category: str) -> dict[str, Species]:
    rows = db.scalars(select(Species).where(Species.category == category)).all()
    return {row.scientific_name.lower(): row for row in rows}


def _species_out(row: Species) -> SpeciesOut:
    """Serialise a species with its gallery and further-reading links.

    The ORM row remains the source of truth for the catalogue text. Images and
    links are additive metadata loaded from committed project files; nothing is
    generated when no free photograph exists.
    """
    payload = SpeciesOut.model_validate(row).model_dump()
    images = species_media.images_for(row.scientific_name)
    payload["images"] = images
    payload["sources"] = species_media.sources_for(
        row.scientific_name, row.common_name, row.category
    )
    payload["odisha_note"] = species_media.odisha_note(row.known_regions)
    if images:
        cover = images[0]
        payload["image_url"] = cover.get("thumbnail_url") or cover.get("url")
        credit = " · ".join(
            part for part in (cover.get("credit"), cover.get("licence")) if part
        )
        payload["image_credit"] = credit or None
    return SpeciesOut(**payload)


def _serialize_observation(
    obs: BiodiversityObservation,
    *,
    session_hash: str | None = None,
    is_admin: bool = False,
) -> ObservationOut:
    latitude, longitude = obs.latitude, obs.longitude
    location_note = None
    if latitude is not None and longitude is not None:
        if obs.derived_sensitive:
            latitude, longitude, _ = geo.obscure_coordinates(
                latitude, longitude, obs.location_precision, True
            )
            location_note = (
                "Coordinates are intentionally approximated because this record is "
                "flagged as potentially sensitive."
            )
        elif obs.location_precision == "approximate":
            location_note = "Approximate coordinates supplied by the observer."
    else:
        location_note = "Location verification unavailable: no coordinates were provided."

    return ObservationOut(
        id=obs.id,
        category=obs.category,
        predicted_species=obs.predicted_species,
        predicted_common_name=obs.predicted_common_name,
        species_id=obs.species_id,
        species=_species_out(obs.species) if obs.species else None,
        confidence_score=obs.confidence_score,
        image_url=image_url(obs.image_path),
        image_quality_status=obs.image_quality_status,
        latitude=latitude,
        longitude=longitude,
        location_precision=obs.location_precision,
        district=obs.district,
        observer_notes=obs.observer_notes,
        verification_status=obs.verification_status,
        review_notes=obs.review_notes,
        consented=obs.consented,
        data_source=obs.data_source,
        model_version=obs.model_version,
        created_at=obs.created_at,
        can_delete=bool(
            is_admin or (session_hash and obs.owner_session_hash == session_hash)
        ),
        location_note=location_note,
    )


async def _read_upload(file: UploadFile) -> bytes:
    if file.content_type and file.content_type not in {
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/octet-stream",
    }:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type. Upload a JPEG, PNG or WEBP image.",
        )
    raw = await file.read(settings.max_upload_bytes + 1)
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image is larger than {settings.max_upload_mb} MB. Please compress it first.",
        )
    if not raw:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    return raw


@router.post("/predict", response_model=PredictionOut)
async def predict(
    request: Request,
    file: Annotated[UploadFile, File(description="Plant or bird photograph")],
    category: Annotated[Literal["plant", "bird"], Form()],
    latitude: Annotated[float | None, Form(ge=-90, le=90)] = None,
    longitude: Annotated[float | None, Form(ge=-180, le=180)] = None,
    district: Annotated[str | None, Form(max_length=120)] = None,
    db: Session = Depends(get_db),
):
    """Validate → assess quality → classify → abstain/flag → explain.

    The endpoint always returns a structured decision. It never invents a label
    when the model is unavailable or the image is unusable.
    """
    upload_limiter.check(client_key(request, "predict"))
    raw = await _read_upload(file)

    try:
        image = load_and_validate(raw)
    except ImageValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    quality = assess_quality(image)
    location_check = LocationCheckOut(
        status="not_provided",
        message="No location supplied; the result is image-only.",
        district=district,
        region_code=None,
    )

    if not quality.usable:
        return PredictionOut(
            model_available=registry.status()["plant"]["available"]
            or registry.status()["bird"]["available"],
            category=category,
            quality=QualityOut(**quality.as_dict()),
            top_predictions=[],
            confidence=None,
            confidence_label=None,
            abstain=True,
            decision="reject",
            abstain_reason=(
                "The image did not pass basic quality checks, so no species "
                "prediction was attempted."
            ),
            location_check=location_check,
            threshold=None,
            explanation=(
                "BioTrace stopped before classification because the photo is too "
                "small, too dark or too blurry to support a trustworthy animal or "
                "plant identification. Try a closer, well-lit, sharply focused photo."
            ),
            limitations=DEFAULT_LIMITATIONS,
            disclaimer=DISCLAIMER,
        )

    try:
        result = registry.predict(image, category, top_k=3)
    except ModelNotAvailable as exc:
        return PredictionOut(
            model_available=False,
            category=category,
            quality=QualityOut(**quality.as_dict()),
            top_predictions=[],
            confidence=None,
            confidence_label=None,
            abstain=True,
            decision="unavailable",
            abstain_reason=exc.reason,
            location_check=location_check,
            threshold=None,
            explanation=(
                "No trained model is installed for this category, so BioTrace cannot "
                "produce a prediction. The image and quality checks still ran. Follow "
                "docs/MODEL_TRAINING.md to train and install a CPU model."
            ),
            limitations=DEFAULT_LIMITATIONS,
            disclaimer=DISCLAIMER,
        )

    species_lookup = _species_map(db, category)
    predictions: list[PredictionClass] = []
    for index, item in enumerate(result["predictions"], start=1):
        record = species_lookup.get(item["label"].lower())
        predictions.append(
            PredictionClass(
                scientific_name=item["label"],
                common_name=record.common_name if record else item["label"],
                confidence=item["confidence"],
                species_id=record.id if record else None,
                rank=index,
            )
        )

    top = predictions[0]
    top_species = species_lookup.get(top.scientific_name.lower())
    known_regions = top_species.known_regions if top_species else None
    geo_result = geo.plausibility_check(known_regions, district, latitude, longitude)
    location_check = LocationCheckOut(**geo_result)  # type: ignore[arg-type]

    threshold = float(result["threshold"])
    reasons: list[str] = []
    if top.confidence < threshold:
        reasons.append(
            f"Top confidence {top.confidence:.0%} is below the validation-selected "
            f"abstention threshold ({threshold:.0%})."
        )
    if result.get("margin") is not None and result["margin"] < 0.08:
        reasons.append("The top two classes are very close, so the model is not decisive.")
    if quality.issues:
        reasons.append("Image quality flags: " + ", ".join(quality.issues) + ".")
    if location_check.status == "outside_known_range":
        reasons.append("The location conflicts with the curated distribution record.")

    decision: Literal["accept", "review", "reject"]
    if location_check.status == "outside_known_range":
        decision = "review"
    elif top.confidence < threshold:
        decision = "review"
    else:
        decision = "accept"

    explanation_bits = [
        f"The {category} model ranked {top.scientific_name} first at "
        f"{top.confidence:.1%} softmax confidence."
    ]
    if len(predictions) > 1:
        explanation_bits.append(
            f"The next candidate is {predictions[1].scientific_name} at "
            f"{predictions[1].confidence:.1%}."
        )
    explanation_bits.append(
        "This is an image-similarity score from a small demonstration model. "
        "It is not calibrated proof, and look-alike species can score highly."
    )
    if decision == "review":
        explanation_bits.append(
            "BioTrace therefore abstains from auto-accepting the identification and "
            "asks for human review."
        )
    else:
        explanation_bits.append(
            "The prediction clears the current threshold, but it should still be "
            "confirmed by a knowledgeable reviewer before being treated as a record."
        )
    if not quality.usable:
        explanation_bits.append("The quality check failed.")

    return PredictionOut(
        model_available=True,
        model_version=result["model_version"],
        category=category,
        quality=QualityOut(**quality.as_dict()),
        top_predictions=predictions,
        confidence=top.confidence,
        confidence_label=_confidence_label(top.confidence),
        abstain=decision != "accept",
        decision=decision,
        abstain_reason=" ".join(reasons) if reasons else None,
        location_check=location_check,
        threshold=threshold,
        explanation=" ".join(explanation_bits),
        limitations=result["limitations"],
        disclaimer=DISCLAIMER,
        model_card=result["model_card"],
    )


@router.get("/species", response_model=list[SpeciesOut])
def list_species(
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[str | None, Query(max_length=120)] = None,
    category: Annotated[Literal["plant", "bird"] | None, Query()] = None,
):
    statement = select(Species).order_by(Species.category, Species.common_name)
    if category:
        statement = statement.where(Species.category == category)
    if q:
        term = f"%{q}%"
        statement = statement.where(
            or_(
                Species.common_name.ilike(term),
                Species.scientific_name.ilike(term),
                Species.description.ilike(term),
            )
        )
    return [_species_out(item) for item in db.scalars(statement).all()]


@router.get("/species/{species_id}", response_model=SpeciesOut)
def species_detail(species_id: int, db: Annotated[Session, Depends(get_db)]):
    species = db.get(Species, species_id)
    if not species:
        raise HTTPException(status_code=404, detail="Species not found in the catalogue.")
    return _species_out(species)


@router.get("/model-status", response_model=ModelStatusOut)
def model_status():
    return ModelStatusOut(**registry.status())


@router.get("/observations", response_model=ObservationListOut)
def list_observations(
    db: Annotated[Session, Depends(get_db)],
    x_session_id: Annotated[str | None, Header()] = None,
    category: Annotated[Literal["plant", "bird"] | None, Query()] = None,
    status_filter: Annotated[
        Literal["pending", "verified", "rejected", "needs_review"] | None,
        Query(alias="status"),
    ] = None,
    district: str | None = None,
    mine: bool = False,
    page: Annotated[int, Query(ge=1, le=1000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 24,
):
    session_hash = hash_session_id(x_session_id) if x_session_id else None
    if mine and not session_hash:
        raise HTTPException(
            status_code=400,
            detail="Missing X-Session-Id header. The web app supplies this automatically.",
        )
    statement = select(BiodiversityObservation).where(
        BiodiversityObservation.consented.is_(True)
    )
    if mine:
        statement = statement.where(BiodiversityObservation.owner_session_hash == session_hash)
    if category:
        statement = statement.where(BiodiversityObservation.category == category)
    if status_filter:
        statement = statement.where(BiodiversityObservation.verification_status == status_filter)
    if district:
        statement = statement.where(BiodiversityObservation.district == district)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.scalars(
        statement.order_by(BiodiversityObservation.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ObservationListOut(
        items=[
            _serialize_observation(row, session_hash=session_hash) for row in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/observations/{observation_id}", response_model=ObservationOut)
def observation_detail(
    observation_id: int,
    db: Annotated[Session, Depends(get_db)],
    x_session_id: Annotated[str | None, Header()] = None,
):
    observation = db.get(BiodiversityObservation, observation_id)
    session_hash = hash_session_id(x_session_id) if x_session_id else None
    if not observation:
        raise HTTPException(status_code=404, detail="Observation not found.")
    is_owner = bool(session_hash and observation.owner_session_hash == session_hash)
    if not observation.consented and not is_owner:
        raise HTTPException(status_code=404, detail="Observation not found.")
    return _serialize_observation(observation, session_hash=session_hash)


@router.post("/observations", response_model=ObservationOut, status_code=201)
async def create_observation(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File()],
    predicted_species: Annotated[str, Form(min_length=2, max_length=160)],
    category: Annotated[Literal["plant", "bird"], Form()],
    confidence_score: Annotated[float, Form(ge=0, le=1)],
    consent: Annotated[bool, Form()],
    predicted_common_name: Annotated[str | None, Form(max_length=160)] = None,
    top_predictions: Annotated[str | None, Form()] = None,
    image_quality_status: Annotated[str, Form(max_length=32)] = "unknown",
    image_quality_notes: Annotated[str | None, Form(max_length=1000)] = None,
    latitude: Annotated[float | None, Form(ge=-90, le=90)] = None,
    longitude: Annotated[float | None, Form(ge=-180, le=180)] = None,
    location_precision: Annotated[
        Literal["exact", "approximate", "district", "none"], Form()
    ] = "none",
    district: Annotated[str | None, Form(max_length=120)] = None,
    observer_notes: Annotated[str | None, Form(max_length=2000)] = None,
    model_version: Annotated[str | None, Form(max_length=80)] = None,
    x_session_id: Annotated[str | None, Header()] = None,
):
    upload_limiter.check(client_key(request, "observe"))
    if not consent:
        raise HTTPException(
            status_code=400,
            detail=(
                "Consent is required to store an observation. You can keep using the "
                "prediction without saving it."
            ),
        )
    if (latitude is None) != (longitude is None):
        raise HTTPException(
            status_code=422,
            detail="Provide both latitude and longitude, or neither.",
        )
    session_hash = require_session_id(x_session_id)

    raw = await _read_upload(file)
    try:
        image = load_and_validate(raw)
    except ImageValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    quality = assess_quality(image)
    if not quality.usable:
        raise HTTPException(
            status_code=422,
            detail=(
                "This image is not clear enough to store as an observation. "
                "Please retake it with better lighting and focus."
            ),
        )

    stored_path = save_observation_image(image)

    resolved_district = district
    precision = location_precision
    if latitude is not None and longitude is not None:
        if not resolved_district and geo.in_odisha(latitude, longitude):
            resolved_district = geo.nearest_district(latitude, longitude)[0]
        if precision == "none":
            precision = "exact"
    else:
        precision = "none" if precision == "exact" else precision

    species = db.scalar(
        select(Species).where(func.lower(Species.scientific_name) == predicted_species.lower())
    )
    derived_sensitive = bool(
        species
        and species.conservation_status
        and any(
            flag in species.conservation_status.lower()
            for flag in ("endangered", "critically endangered", "vulnerable")
        )
    )

    observation = BiodiversityObservation(
        species_id=species.id if species else None,
        predicted_species=predicted_species,
        predicted_common_name=predicted_common_name or (species.common_name if species else None),
        category=category,
        confidence_score=confidence_score,
        top_predictions_json=top_predictions,
        image_path=stored_path,
        image_quality_status=image_quality_status,
        image_quality_notes=image_quality_notes,
        latitude=latitude,
        longitude=longitude,
        location_precision=precision,
        district=resolved_district,
        observer_notes=observer_notes,
        verification_status="pending",
        consented=True,
        data_source="user_upload",
        model_version=model_version,
        derived_sensitive=derived_sensitive,
        owner_session_hash=session_hash,
    )
    db.add(observation)
    db.commit()
    db.refresh(observation)
    return _serialize_observation(observation, session_hash=session_hash)


@router.delete("/observations/{observation_id}", status_code=204)
def delete_observation(
    observation_id: int,
    db: Annotated[Session, Depends(get_db)],
    x_session_id: Annotated[str | None, Header()] = None,
):
    observation = db.get(BiodiversityObservation, observation_id)
    if not observation:
        raise HTTPException(status_code=404, detail="Observation not found.")
    session_hash = hash_session_id(x_session_id) if x_session_id else None
    if not session_hash or observation.owner_session_hash != session_hash:
        raise HTTPException(
            status_code=403,
            detail=(
                "Only the device that submitted this observation can delete it. "
                "Use the same browser profile or contact the project maintainer."
            ),
        )
    path = observation.image_path
    db.delete(observation)
    db.commit()
    delete_observation_image(path)
    return None
