"""Destination photographs: storage, API exposure, attestation and importer rules."""

from __future__ import annotations

import json
import urllib.parse

import pytest

from backend.app import models
from backend.app.seed import IMAGES_FILE, seed_destination_images, seed_destinations
from backend.scripts import fetch_images


def _image(destination_id: int, order: int = 0, **overrides) -> models.DestinationImage:
    payload = {
        "destination_id": destination_id,
        "url": f"https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Photo-{order}.jpg/1600px-Photo-{order}.jpg",
        "thumbnail_url": f"https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Photo-{order}.jpg/640px-Photo-{order}.jpg",
        "page_url": f"https://commons.wikimedia.org/wiki/File:Photo-{order}.jpg",
        "title": f"Photo {order}",
        "credit": "A Photographer",
        "licence": "CC BY-SA 4.0",
        "licence_url": "https://creativecommons.org/licenses/by-sa/4.0",
        "width": 1600,
        "height": 900,
        "sort_order": order,
        "source_name": "Wikimedia Commons",
    }
    payload.update(overrides)
    return models.DestinationImage(**payload)


@pytest.fixture()
def with_images(destination, db):
    db.add_all([_image(destination.id, 0), _image(destination.id, 1, title="Second photo")])
    db.commit()
    return destination


# --------------------------------------------------------------------------- #
# API exposure
# --------------------------------------------------------------------------- #
def test_detail_returns_ordered_credited_images(client, with_images):
    body = client.get("/api/tourism/destinations/barabati-fort").json()
    assert [item["title"] for item in body["images"]] == ["Photo 0", "Second photo"]
    first = body["images"][0]
    assert first["page_url"].startswith("https://commons.wikimedia.org/wiki/File:")
    assert first["licence"] == "CC BY-SA 4.0"
    assert first["credit"] == "A Photographer"
    assert first["thumbnail_url"]


def test_list_exposes_a_cover_image_for_cards(client, with_images):
    item = client.get("/api/tourism/destinations").json()["items"][0]
    assert item["cover_image"].endswith("1600px-Photo-0.jpg")
    assert item["cover_image_thumbnail"].endswith("640px-Photo-0.jpg")
    assert item["cover_image_credit"] == "A Photographer"
    assert item["cover_image_licence"] == "CC BY-SA 4.0"


def test_destination_without_photos_has_no_cover(client, destination):
    item = client.get("/api/tourism/destinations").json()["items"][0]
    assert item["cover_image"] is None
    assert item["cover_image_thumbnail"] is None


def test_photos_satisfy_the_reusable_photograph_gap(client, with_images):
    body = client.get("/api/tourism/destinations/barabati-fort").json()
    assert "Reusable photograph" not in body["data_gaps"]


def test_missing_photo_is_still_reported_as_a_gap(client, destination):
    body = client.get("/api/tourism/destinations/barabati-fort").json()
    assert "Reusable photograph" in body["data_gaps"]


def test_home_dashboard_cards_include_covers(client, with_images):
    body = client.get("/api/home").json()
    assert body["featured"][0]["cover_image"].endswith("1600px-Photo-0.jpg")


def test_deleting_a_destination_cascades_its_photos(client, with_images, db):
    db.delete(db.get(models.TourismDestination, with_images.id))
    db.commit()
    assert db.query(models.DestinationImage).count() == 0


# --------------------------------------------------------------------------- #
# Seeding from committed metadata
# --------------------------------------------------------------------------- #
def test_seed_images_attach_from_the_committed_file(db):
    seed_destinations(db)
    created = seed_destination_images(db)
    assert created > 0
    assert db.query(models.DestinationImage).count() == created

    # A second pass must not duplicate rows.
    assert seed_destination_images(db) == 0


def test_seed_images_skips_records_without_provenance(db, monkeypatch, tmp_path):
    seed_destinations(db)
    broken = {
        "places": {
            "barabati-fort": [
                {"url": "https://example.org/a.jpg", "page_url": "https://example.org/a", "licence": None},
                {"url": "https://example.org/b.jpg", "page_url": "https://example.org/b", "licence": "CC BY 4.0", "credit": "X"},
            ]
        }
    }
    path = tmp_path / "images.json"
    path.write_text(json.dumps(broken), encoding="utf-8")
    monkeypatch.setattr("backend.app.seed.IMAGES_FILE", path)

    assert seed_destination_images(db) == 1
    stored = db.query(models.DestinationImage).one()
    assert stored.url.endswith("/b.jpg")


def test_committed_image_file_is_well_formed():
    payload = json.loads(IMAGES_FILE.read_text(encoding="utf-8"))
    assert payload["source"] == "Wikimedia Commons"
    assert payload["places"]

    seen: set[str] = set()
    for slug, images in payload["places"].items():
        assert isinstance(images, list), slug
        for image in images:
            host = urllib.parse.urlsplit(image["url"]).hostname or ""
            assert host.endswith(".wikimedia.org"), (slug, image["url"])
            assert "?" not in image["url"], (slug, image["url"])
            assert image["page_url"].startswith("https://commons.wikimedia.org/"), slug
            assert fetch_images.is_free_licence(image["licence"]), (slug, image["licence"])
            assert image["credit"] or "cc0" in image["licence"].lower(), slug
            assert image["page_url"] not in seen, f"duplicate image in {slug}"
            seen.add(image["page_url"])


# --------------------------------------------------------------------------- #
# Importer rules
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("licence", "expected"),
    [
        ("CC BY-SA 4.0", True),
        ("CC BY 2.0", True),
        ("CC0", True),
        ("Public domain", True),
        ("Fair use", False),
        ("All rights reserved", False),
        (None, False),
        ("", False),
    ],
)
def test_is_free_licence(licence, expected):
    assert fetch_images.is_free_licence(licence) is expected


def _candidate(**overrides) -> dict:
    base = {
        "title": "Barabati Fort, Cuttack",
        "raw_title": "File:Barabati Fort, Cuttack.jpg",
        "url": "https://upload.wikimedia.org/a/1600px-x.jpg",
        "thumbnail_url": "https://upload.wikimedia.org/a/1600px-x.jpg",
        "page_url": "https://commons.wikimedia.org/wiki/File:X.jpg",
        "credit": "Someone",
        "licence": "CC BY-SA 4.0",
        "licence_url": "https://creativecommons.org/licenses/by-sa/4.0",
        "width": 1600,
        "height": 900,
        "original_width": 4000,
        "original_height": 2250,
        "categories": "Quality images",
    }
    base.update(overrides)
    return base


def test_candidate_accepts_a_landscape_photo_of_the_place():
    assert fetch_images.candidate_is_usable(_candidate(), "Barabati Fort")


def test_candidate_rejects_a_pdf_scan_rendered_as_a_jpeg():
    scan = _candidate(raw_title="File:The American Baptist magazine.pdf", title="The American Baptist magazine")
    assert fetch_images.candidate_is_usable(scan, "Baptist Church") is False


def test_candidate_rejects_document_categories():
    scan = _candidate(categories="PDF files, Scanned books")
    assert fetch_images.candidate_is_usable(scan, "Barabati Fort") is False


def test_candidate_rejects_unrelated_titles():
    other = _candidate(title="Konark Sun Temple", raw_title="File:Konark.jpg")
    assert fetch_images.candidate_is_usable(other, "Barabati Fort") is False


def test_candidate_rejects_a_map_or_logo():
    logo = _candidate(title="Barabati Fort logo", raw_title="File:Barabati Fort logo.png")
    assert fetch_images.candidate_is_usable(logo, "Barabati Fort") is False


def test_candidate_requires_credit_for_cc_by():
    assert fetch_images.candidate_is_usable(_candidate(credit=None), "Barabati Fort") is False


def test_candidate_allows_no_credit_for_public_domain():
    pd = _candidate(credit=None, licence="Public domain")
    assert fetch_images.candidate_is_usable(pd, "Barabati Fort") is True


def test_candidate_rejects_low_resolution_originals():
    small = _candidate(original_width=800, original_height=600)
    assert fetch_images.candidate_is_usable(small, "Barabati Fort") is False


def test_select_prefers_landscape_then_fills_with_portrait():
    landscape = _candidate(page_url="https://c/1", title="Barabati Fort front")
    portrait = _candidate(
        page_url="https://c/2",
        raw_title="File:Barabati Fort tower.jpg",
        title="Barabati Fort tower",
        original_width=2000,
        original_height=3000,
        width=1000,
        height=1500,
    )
    chosen = fetch_images.select_images([portrait, landscape], "Barabati Fort", 5)
    assert chosen[0]["page_url"] == "https://c/1"
    assert len(chosen) == 2


def test_select_deduplicates_by_file_page():
    first = _candidate()
    second = _candidate(title="Barabati Fort again")
    chosen = fetch_images.select_images([first, second], "Barabati Fort", 5)
    assert len(chosen) == 1


def test_slugify_matches_the_seed_slugs():
    assert fetch_images.slugify("Barabati Fort") == "barabati-fort"
    assert fetch_images.slugify("Baptist Church, Cuttack") == "baptist-church-cuttack"
    assert fetch_images.slugify("Maa & Temple") == "maa-and-temple"


def test_build_queries_tries_several_phrasings_without_duplicates():
    place = {"name": "Barabati Fort", "district": "Cuttack", "query": "Barabati Fort Cuttack"}
    queries = fetch_images.build_queries(place)
    assert queries[0] == "Barabati Fort Cuttack"
    assert "Barabati Fort Odisha" in queries
    assert "Barabati Fort" in queries
    assert len(queries) == len(set(queries))
