"""Anonymous per-session features: favourites and itineraries."""

from __future__ import annotations

SESSION_A = {"X-Session-Id": "session-aaaaaaaa"}
SESSION_B = {"X-Session-Id": "session-bbbbbbbb"}


# --------------------------------------------------------------------------- #
# Favourites
# --------------------------------------------------------------------------- #
def test_favourites_require_a_session_header(client, destination):
    assert client.get("/api/favourites").status_code == 400
    assert client.post(f"/api/favourites/{destination.id}").status_code == 400


def test_add_list_and_remove_favourite(client, destination):
    created = client.post(f"/api/favourites/{destination.id}", headers=SESSION_A)
    assert created.status_code == 201
    assert created.json()["destination"]["slug"] == "barabati-fort"

    listed = client.get("/api/favourites", headers=SESSION_A).json()
    assert [item["destination"]["id"] for item in listed] == [destination.id]

    assert client.delete(
        f"/api/favourites/{destination.id}", headers=SESSION_A
    ).status_code == 204
    assert client.get("/api/favourites", headers=SESSION_A).json() == []


def test_adding_the_same_favourite_is_idempotent(client, destination):
    first = client.post(f"/api/favourites/{destination.id}", headers=SESSION_A).json()
    second = client.post(f"/api/favourites/{destination.id}", headers=SESSION_A).json()
    assert first["id"] == second["id"]
    assert len(client.get("/api/favourites", headers=SESSION_A).json()) == 1


def test_favourites_are_isolated_between_sessions(client, destination):
    client.post(f"/api/favourites/{destination.id}", headers=SESSION_A)
    assert client.get("/api/favourites", headers=SESSION_B).json() == []


def test_favourite_unknown_destination_is_404(client):
    assert client.post("/api/favourites/9999", headers=SESSION_A).status_code == 404


def test_removing_a_favourite_that_was_never_saved_is_404(client, destination):
    assert client.delete(
        f"/api/favourites/{destination.id}", headers=SESSION_A
    ).status_code == 404


def test_session_id_length_is_validated(client):
    short = client.get("/api/favourites", headers={"X-Session-Id": "short"})
    assert short.status_code == 400
    assert "8 and 128" in short.json()["detail"]


# --------------------------------------------------------------------------- #
# Itineraries
# --------------------------------------------------------------------------- #
def test_create_itinerary_with_ordered_stops(client, destination, db):
    import backend.app.models as models

    second = models.TourismDestination(
        name="Lingaraj Temple",
        slug="lingaraj-temple",
        category="temple",
        district="Khordha",
        latitude=20.2382,
        longitude=85.8337,
        estimated_visit_minutes=45,
        verification_status="verified",
    )
    db.add(second)
    db.commit()
    db.refresh(second)

    response = client.post(
        "/api/itineraries",
        headers=SESSION_A,
        json={
            "title": "Cuttack and Bhubaneswar",
            "travel_date": "2026-11-01",
            "notes": "Two easy days.",
            "stops": [
                {"destination_id": destination.id, "notes": "Morning"},
                {"destination_id": second.id},
            ],
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert [stop["stop_order"] for stop in body["stops"]] == [0, 1]
    assert body["stops"][0]["destination"]["slug"] == "barabati-fort"
    assert body["total_estimated_minutes"] == 105
    assert body["disclaimer"]


def test_itinerary_total_minutes_is_null_when_an_estimate_is_missing(
    client, destination, db
):
    import backend.app.models as models

    db.add(
        models.TourismDestination(
            name="Unmeasured Spot",
            slug="unmeasured-spot",
            category="other",
            district="Khordha",
            verification_status="provisional",
        )
    )
    db.commit()
    spot = db.query(models.TourismDestination).filter_by(slug="unmeasured-spot").one()

    body = client.post(
        "/api/itineraries",
        headers=SESSION_A,
        json={"title": "Gap trip", "stops": [{"destination_id": spot.id}]},
    ).json()
    assert body["total_estimated_minutes"] is None


def test_itinerary_rejects_duplicate_stops(client, destination):
    response = client.post(
        "/api/itineraries",
        headers=SESSION_A,
        json={
            "title": "Duplicate trip",
            "stops": [
                {"destination_id": destination.id},
                {"destination_id": destination.id},
            ],
        },
    )
    assert response.status_code == 422


def test_itinerary_rejects_unknown_destination(client):
    response = client.post(
        "/api/itineraries",
        headers=SESSION_A,
        json={"title": "Ghost trip", "stops": [{"destination_id": 9999}]},
    )
    assert response.status_code == 422


def test_itinerary_rejects_implausible_travel_date(client):
    response = client.post(
        "/api/itineraries",
        headers=SESSION_A,
        json={"title": "Time traveller", "travel_date": "1900-01-01"},
    )
    assert response.status_code == 422


def test_itinerary_update_replaces_stops(client, destination):
    created = client.post(
        "/api/itineraries",
        headers=SESSION_A,
        json={"title": "First plan", "stops": [{"destination_id": destination.id}]},
    ).json()

    updated = client.put(
        f"/api/itineraries/{created['id']}",
        headers=SESSION_A,
        json={"title": "Renamed plan", "stops": []},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Renamed plan"
    assert updated.json()["stops"] == []


def test_itineraries_are_isolated_between_sessions(client, destination):
    created = client.post(
        "/api/itineraries",
        headers=SESSION_A,
        json={"title": "Private plan", "stops": [{"destination_id": destination.id}]},
    ).json()

    assert client.get("/api/itineraries", headers=SESSION_B).json() == []
    assert client.get(f"/api/itineraries/{created['id']}", headers=SESSION_B).status_code == 404
    assert client.delete(
        f"/api/itineraries/{created['id']}", headers=SESSION_B
    ).status_code == 404


def test_delete_itinerary_cascades_stops(client, destination, db):
    import backend.app.models as models

    created = client.post(
        "/api/itineraries",
        headers=SESSION_A,
        json={"title": "Temporary plan", "stops": [{"destination_id": destination.id}]},
    ).json()

    assert client.delete(f"/api/itineraries/{created['id']}", headers=SESSION_A).status_code == 204
    assert db.query(models.ItineraryStop).count() == 0
