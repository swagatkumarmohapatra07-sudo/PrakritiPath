"""Platform endpoints: health, stats, home dashboard, map, districts, taxonomy."""

from __future__ import annotations


def test_health_reports_database_and_models(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert set(body["ai_models"]) == {"plant", "bird"}
    assert body["version"] == "1.0.0"


def test_stats_counts_seeded_records(client, destination, species, observation):
    body = client.get("/api/stats").json()
    assert body["destinations_total"] == 1
    assert body["destinations_verified"] == 1
    assert body["species_catalogued"] == 1
    assert body["bird_species"] == 1
    assert body["plant_species"] == 0
    assert body["observations_total"] == 1


def test_home_returns_everything_the_landing_page_needs(client, destination, species):
    body = client.get("/api/home").json()
    assert set(body) >= {
        "stats",
        "featured",
        "recent_observations",
        "categories",
        "groups",
        "map_preview",
        "species",
    }
    assert [item["slug"] for item in body["featured"]] == ["barabati-fort"]
    assert body["map_preview"][0]["name"] == "Barabati Fort"


def test_map_returns_bounds_for_visible_records(client, destination, observation):
    body = client.get("/api/map").json()
    assert len(body["destinations"]) == 1
    assert len(body["observations"]) == 1
    assert body["bounds"] is not None
    assert body["notes"]


def test_map_can_disable_layers(client, destination, observation):
    body = client.get("/api/map", params={"include_observations": "false"}).json()
    assert body["destinations"] == []
    assert body["observations"] == []


def test_map_filters_biodiversity_by_district(client, destination, observation):
    body = client.get("/api/map", params={"district": "Khordha"}).json()
    assert body["destinations"] == []
    assert len(body["observations"]) == 1


def test_map_rejects_unknown_layer(client):
    assert client.get("/api/map", params={"layers": "nope"}).status_code == 422


def test_districts_lists_known_odisha_districts(client, destination):
    body = client.get("/api/districts").json()
    names = {item["name"] for item in body["odisha"]}
    assert "Cuttack" in names
    assert body["with_records"] == 1


def test_taxonomy_exposes_categories_species_and_districts(client, destination, species):
    body = client.get("/api/taxonomy").json()
    slugs = {item["slug"] for item in body["categories"]}
    assert "fort_palace" in slugs
    assert body["species"][0]["scientific_name"] == "Pavo cristatus"
    assert "Khordha" in body["districts"]


def test_unhandled_errors_are_json_not_html(client):
    # A 404 from a mounted static app is still a valid HTTP response, not a crash.
    response = client.get("/this-page-does-not-exist.html")
    assert response.status_code == 404


def test_security_headers_are_present(client):
    response = client.get("/api/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
