"""Admin authentication, review queue and public report intake."""

from __future__ import annotations

ADMIN = {"username": "admin", "password": "test-password"}


def _token(client) -> str:
    response = client.post("/api/admin/login", json=ADMIN)
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth(client) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(client)}"}


# --------------------------------------------------------------------------- #
# Authentication
# --------------------------------------------------------------------------- #
def test_admin_login_returns_a_bearer_token(client):
    body = client.post("/api/admin/login", json=ADMIN).json()
    assert body["token_type"] == "bearer"
    assert body["username"] == "admin"
    assert body["expires_in_minutes"] == 60
    assert body["access_token"]


def test_admin_login_rejects_wrong_password(client):
    response = client.post(
        "/api/admin/login", json={"username": "admin", "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


def test_admin_routes_require_a_token(client):
    for path in (
        "/api/admin/overview",
        "/api/admin/observations",
        "/api/admin/destinations",
        "/api/admin/reports",
    ):
        assert client.get(path).status_code == 401, path


def test_admin_rejects_a_forged_token(client):
    response = client.get(
        "/api/admin/overview", headers={"Authorization": "Bearer not.a.real.token"}
    )
    assert response.status_code == 401


def test_admin_rejects_a_tampered_signature(client, db):
    from backend.app.security import create_admin_token

    token = create_admin_token("admin")
    body, signature = token.split(".")
    forged = f"{body}.{'A' * len(signature)}"
    response = client.get(
        "/api/admin/overview", headers={"Authorization": f"Bearer {forged}"}
    )
    assert response.status_code == 401


def test_expired_admin_token_is_rejected(client):
    from backend.app.security import create_admin_token

    token = create_admin_token("admin", ttl_minutes=-1)
    response = client.get(
        "/api/admin/overview", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


# --------------------------------------------------------------------------- #
# Review queue
# --------------------------------------------------------------------------- #
def test_overview_counts_pending_work(client, destination, observation, db):
    import backend.app.models as models

    db.add(
        models.ReviewReport(
            record_type="destination",
            record_id=destination.id,
            report_reason="stale_hours",
            status="open",
        )
    )
    db.commit()

    body = client.get("/api/admin/overview", headers=_auth(client)).json()
    assert body["pending_observations"] == 1
    assert body["open_reports"] == 1
    assert body["total_observations"] == 1
    assert body["total_destinations"] == 1


def test_admin_can_verify_an_observation_and_action_is_logged(
    client, observation, db
):
    import backend.app.models as models

    headers = _auth(client)
    response = client.patch(
        f"/api/admin/observations/{observation.id}",
        headers=headers,
        json={"verification_status": "verified", "review_notes": "Looks right."},
    )
    assert response.status_code == 200

    db.expire_all()
    refreshed = db.get(models.BiodiversityObservation, observation.id)
    assert refreshed.verification_status == "verified"
    assert refreshed.review_notes == "Looks right."

    audit = db.query(models.ReviewReport).filter_by(report_reason="admin_review").one()
    assert audit.status == "resolved"


def test_admin_can_correct_the_species_on_an_observation(client, observation, db):
    import backend.app.models as models

    corrected = models.Species(
        common_name="House Crow",
        scientific_name="Corvus splendens",
        category="bird",
    )
    db.add(corrected)
    db.commit()
    db.refresh(corrected)

    response = client.patch(
        f"/api/admin/observations/{observation.id}",
        headers=_auth(client),
        json={"verification_status": "needs_review", "species_id": corrected.id},
    )
    assert response.status_code == 200

    db.expire_all()
    refreshed = db.get(models.BiodiversityObservation, observation.id)
    assert refreshed.predicted_species == "Corvus splendens"
    assert refreshed.species_id == corrected.id


def test_admin_cannot_assign_a_missing_species(client, observation):
    response = client.patch(
        f"/api/admin/observations/{observation.id}",
        headers=_auth(client),
        json={"verification_status": "verified", "species_id": 9999},
    )
    assert response.status_code == 422


def test_admin_can_update_destination_status(client, destination, db):
    import backend.app.models as models

    response = client.patch(
        f"/api/admin/destinations/{destination.id}",
        headers=_auth(client),
        json={"verification_status": "needs_review", "note": "Check the hours."},
    )
    assert response.status_code == 200

    db.expire_all()
    refreshed = db.get(models.TourismDestination, destination.id)
    assert refreshed.verification_status == "needs_review"


def test_admin_report_queue_and_status_update(client, destination, db):
    import backend.app.models as models

    report = models.ReviewReport(
        record_type="destination",
        record_id=destination.id,
        report_reason="stale_hours",
        status="open",
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    headers = _auth(client)
    queue = client.get("/api/admin/reports", params={"status_filter": "open"}, headers=headers).json()
    assert [item["id"] for item in queue] == [report.id]

    detail = client.get(f"/api/admin/reports/{report.id}", headers=headers).json()
    assert detail["reason"] == "stale_hours"

    updated = client.patch(
        f"/api/admin/reports/{report.id}", headers=headers, json={"status": "resolved"}
    )
    assert updated.status_code == 200


# --------------------------------------------------------------------------- #
# Public report intake
# --------------------------------------------------------------------------- #
def test_public_report_is_created_as_open(client, destination):
    response = client.post(
        "/api/reports",
        headers={"X-Session-Id": "session-aaaaaaaa"},
        json={
            "record_type": "destination",
            "record_id": destination.id,
            "record_label": "Barabati Fort",
            "report_reason": "stale_hours",
            "report_details": "The gate closed at 5pm, not 6pm.",
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "open"


def test_public_report_for_missing_record_is_404(client):
    response = client.post(
        "/api/reports",
        json={"record_type": "destination", "record_id": 9999, "report_reason": "stale_hours"},
    )
    assert response.status_code == 404


def test_public_report_validates_record_type_and_reason(client):
    bad_type = client.post(
        "/api/reports", json={"record_type": "nonsense", "report_reason": "stale_hours"}
    )
    assert bad_type.status_code == 422

    bad_reason = client.post(
        "/api/reports", json={"record_type": "species", "report_reason": "x"}
    )
    assert bad_reason.status_code == 422


def test_my_reports_are_scoped_to_the_session(client, destination):
    headers = {"X-Session-Id": "session-aaaaaaaa"}
    client.post(
        "/api/reports",
        headers=headers,
        json={"record_type": "destination", "record_id": destination.id, "report_reason": "stale_hours"},
    )

    mine = client.get("/api/reports/mine", headers=headers).json()
    assert len(mine) == 1

    other = client.get(
        "/api/reports/mine", headers={"X-Session-Id": "session-bbbbbbbb"}
    ).json()
    assert other == []


def test_my_reports_requires_a_session(client):
    assert client.get("/api/reports/mine").status_code == 400
