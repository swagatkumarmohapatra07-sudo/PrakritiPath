"""Biodiversity API: species catalogue, honest model status, predictions, observations."""

from __future__ import annotations

import io

import numpy as np
from PIL import Image


def _good_photo() -> bytes:
    """A noisy but usable image: mid brightness, high contrast, plenty of edges."""
    rng = np.random.default_rng(42)
    array = rng.integers(0, 256, size=(600, 800, 3), dtype=np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(array).save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


def _unusable_photo() -> bytes:
    """A flat grey square: low resolution, no contrast, no edges."""
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), (128, 128, 128)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_species_list_returns_catalogue(client, species):
    body = client.get("/api/biodiversity/species").json()
    assert len(body) == 1
    assert body[0]["scientific_name"] == "Pavo cristatus"


def test_species_list_filters_by_category_and_query(client, species):
    assert len(client.get("/api/biodiversity/species", params={"category": "bird"}).json()) == 1
    assert client.get("/api/biodiversity/species", params={"category": "plant"}).json() == []
    assert len(client.get("/api/biodiversity/species", params={"q": "peafowl"}).json()) == 1


def test_species_detail_and_404(client, species):
    assert client.get(f"/api/biodiversity/species/{species.id}").json()["id"] == species.id
    assert client.get("/api/biodiversity/species/9999").status_code == 404


def test_model_status_is_honest_when_no_weights_installed(client):
    body = client.get("/api/biodiversity/model-status").json()
    assert body["plant"]["available"] is False
    assert body["bird"]["available"] is False
    assert "torch_installed" in body


def test_predict_reports_unavailable_instead_of_inventing_a_label(client):
    response = client.post(
        "/api/biodiversity/predict",
        files={"file": ("leaf.jpg", _good_photo(), "image/jpeg")},
        data={"category": "plant"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["model_available"] is False
    assert body["decision"] == "unavailable"
    assert body["abstain"] is True
    assert body["top_predictions"] == []
    assert body["confidence"] is None
    assert body["abstain_reason"]


def test_predict_rejects_an_unusable_image_before_classification(client):
    response = client.post(
        "/api/biodiversity/predict",
        files={"file": ("flat.png", _unusable_photo(), "image/png")},
        data={"category": "bird"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["quality"]["usable"] is False
    assert body["decision"] == "reject"
    assert {"low_resolution", "blurry"} & set(body["quality"]["issues"])


def test_predict_rejects_non_image_uploads(client):
    response = client.post(
        "/api/biodiversity/predict",
        files={"file": ("notes.txt", b"this is not an image", "text/plain")},
        data={"category": "plant"},
    )
    assert response.status_code == 415


def test_predict_rejects_corrupt_image_bytes(client):
    response = client.post(
        "/api/biodiversity/predict",
        files={"file": ("broken.jpg", b"\xff\xd8\xff\xe0not-really-a-jpeg", "image/jpeg")},
        data={"category": "plant"},
    )
    assert response.status_code == 422


def test_observation_list_only_shows_consented_records(client, observation, db):
    import backend.app.models as models

    db.add(
        models.BiodiversityObservation(
            predicted_species="Hidden species",
            category="plant",
            confidence_score=0.5,
            image_path="observations/hidden.jpg",
            consented=False,
        )
    )
    db.commit()

    body = client.get("/api/biodiversity/observations").json()
    assert body["total"] == 1
    assert body["items"][0]["predicted_species"] == "Pavo cristatus"


def test_observation_mine_requires_a_session_header(client):
    response = client.get("/api/biodiversity/observations", params={"mine": "true"})
    assert response.status_code == 400


def test_create_observation_requires_consent(client):
    response = client.post(
        "/api/biodiversity/observations",
        headers={"X-Session-Id": "test-session-0001"},
        files={"file": ("bird.jpg", _good_photo(), "image/jpeg")},
        data={
            "predicted_species": "Pavo cristatus",
            "category": "bird",
            "confidence_score": "0.9",
            "consent": "false",
        },
    )
    assert response.status_code == 400


def test_create_observation_strips_exif_and_tracks_owner(client, species):
    headers = {"X-Session-Id": "test-session-0001"}
    response = client.post(
        "/api/biodiversity/observations",
        headers=headers,
        files={"file": ("bird.jpg", _good_photo(), "image/jpeg")},
        data={
            "predicted_species": "Pavo cristatus",
            "category": "bird",
            "confidence_score": "0.9",
            "consent": "true",
            "latitude": "20.2961",
            "longitude": "85.8245",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["verification_status"] == "pending"
    assert body["species_id"] == species.id
    assert body["district"] == "Khordha"
    assert body["can_delete"] is True
    assert body["image_url"].startswith("/media/observations/")

    # Another browser session must not be allowed to delete it.
    other = client.delete(
        f"/api/biodiversity/observations/{body['id']}",
        headers={"X-Session-Id": "someone-else-9999"},
    )
    assert other.status_code == 403

    owner = client.delete(
        f"/api/biodiversity/observations/{body['id']}",
        headers=headers,
    )
    assert owner.status_code == 204


def test_create_observation_rejects_half_a_coordinate(client):
    response = client.post(
        "/api/biodiversity/observations",
        headers={"X-Session-Id": "test-session-0001"},
        files={"file": ("bird.jpg", _good_photo(), "image/jpeg")},
        data={
            "predicted_species": "Pavo cristatus",
            "category": "bird",
            "confidence_score": "0.9",
            "consent": "true",
            "latitude": "20.2961",
        },
    )
    assert response.status_code == 422


def test_observation_detail_hides_unconsented_records_from_other_sessions(
    client, db
):
    import backend.app.models as models

    hidden = models.BiodiversityObservation(
        predicted_species="Hidden species",
        category="plant",
        confidence_score=0.5,
        image_path="observations/hidden.jpg",
        consented=False,
        owner_session_hash="not-mine",
    )
    db.add(hidden)
    db.commit()
    db.refresh(hidden)

    assert client.get(f"/api/biodiversity/observations/{hidden.id}").status_code == 404
