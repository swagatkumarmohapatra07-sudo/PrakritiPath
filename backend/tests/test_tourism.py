"""Tourism discovery API: listing, filters, detail, nearby, map, suggestions."""

from __future__ import annotations


def test_list_destinations_returns_paginated_envelope(client, destination):
    body = client.get("/api/tourism/destinations").json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["has_more"] is False
    assert body["items"][0]["slug"] == "barabati-fort"


def test_list_destinations_searches_name_city_and_district(client, destination):
    for term in ("Barabati", "Cuttack", "medieval"):
        body = client.get("/api/tourism/destinations", params={"q": term}).json()
        assert body["total"] == 1, term


def test_list_destinations_filters_by_known_category(client, destination):
    body = client.get("/api/tourism/destinations", params={"category": "fort_palace"}).json()
    assert body["total"] == 1


def test_list_destinations_rejects_unknown_category(client):
    response = client.get("/api/tourism/destinations", params={"category": "made-up"})
    assert response.status_code == 422
    assert "Unknown category" in response.json()["detail"]


def test_list_destinations_filters_by_district_and_featured(client, destination):
    assert client.get(
        "/api/tourism/destinations", params={"district": "Cuttack"}
    ).json()["total"] == 1
    assert client.get(
        "/api/tourism/destinations", params={"featured": "true"}
    ).json()["total"] == 1
    assert client.get(
        "/api/tourism/destinations", params={"district": "Puri"}
    ).json()["total"] == 0


def test_destination_detail_by_slug_reports_data_gaps(client, destination):
    body = client.get("/api/tourism/destinations/barabati-fort").json()
    assert body["name"] == "Barabati Fort"
    assert body["district"] == "Cuttack"
    # Fields the seed record does not provide must be surfaced, never invented.
    assert "Entry fee" in body["data_gaps"]
    assert "Visiting hours" in body["data_gaps"]
    assert body["nearby"] == []


def test_destination_detail_by_numeric_id(client, destination):
    body = client.get(f"/api/tourism/destinations/{destination.id}").json()
    assert body["id"] == destination.id


def test_destination_detail_returns_404_for_missing_record(client):
    response = client.get("/api/tourism/destinations/does-not-exist")
    assert response.status_code == 404


def test_nearby_endpoint_respects_radius(client, destination, db):
    import backend.app.models as models

    db.add(
        models.TourismDestination(
            name="Far Away Temple",
            slug="far-away-temple",
            category="temple",
            district="Puri",
            latitude=19.8135,
            longitude=85.8312,
            verification_status="verified",
        )
    )
    db.commit()

    # ~80 km away: excluded by the default 25 km radius …
    near = client.get("/api/tourism/nearby", params={"lat": 20.4847, "lon": 85.8649}).json()
    assert "far-away-temple" not in [item["slug"] for item in near]

    # … but included once the radius covers it, with a computed distance.
    wide = client.get(
        "/api/tourism/nearby",
        params={"lat": 20.4847, "lon": 85.8649, "radius_km": 200},
    ).json()
    assert "far-away-temple" in [item["slug"] for item in wide]
    far = next(item for item in wide if item["slug"] == "far-away-temple")
    assert far["distance_km"] is not None
    assert far["distance_km"] > 25


def test_tourism_map_returns_markers_and_bounds(client, destination):
    body = client.get("/api/tourism/map").json()
    assert len(body["destinations"]) == 1
    assert body["bounds"]["min_lat"] == 20.4847
    assert body["observations"] == []


def test_categories_include_counts(client, destination):
    body = client.get("/api/tourism/categories").json()
    fort = next(item for item in body if item["slug"] == "fort_palace")
    assert fort["count"] == 1


def test_collections_only_return_real_records(client, destination):
    body = client.get("/api/tourism/collections").json()
    assert isinstance(body, list)
    for group in body:
        # Cuttack is not part of the curated groups, so nothing is fabricated.
        assert group["places"] == []


def test_suggestion_is_accepted_and_not_published(client):
    response = client.post(
        "/api/tourism/suggestions",
        json={
            "name": "A New Place",
            "category": "temple",
            "district": "Khordha",
            "description": "Submitted during tests.",
            "consent": True,
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] in {"pending", "received", "open"}

    # Suggestions must never leak into the public catalogue.
    assert client.get(
        "/api/tourism/destinations", params={"q": "A New Place"}
    ).json()["total"] == 0


def test_suggestion_requires_consent(client):
    response = client.post(
        "/api/tourism/suggestions",
        json={"name": "No Consent", "category": "temple", "consent": False},
    )
    assert response.status_code == 400
    assert "consent" in response.json()["detail"].lower()


def test_correction_is_recorded_against_an_existing_destination(client, destination):
    response = client.post(
        "/api/tourism/corrections",
        json={
            "destination_id": destination.id,
            "field_name": "entry_fee",
            "suggested_value": "Free",
            "explanation": "Test correction.",
        },
    )
    assert response.status_code == 201


def test_correction_for_unknown_destination_is_rejected(client):
    response = client.post(
        "/api/tourism/corrections",
        json={"destination_id": 9999, "field_name": "entry_fee", "suggested_value": "Free"},
    )
    assert response.status_code == 404
