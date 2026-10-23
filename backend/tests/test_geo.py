"""Pure geo helpers: distance, district lookup, plausibility, coordinate obscuring."""

from __future__ import annotations

import pytest

from backend.app.services import geo


def test_haversine_matches_a_known_distance():
    # Cuttack to Bhubaneswar is roughly 20 km as the crow flies.
    distance = geo.haversine_km(20.4625, 85.8830, 20.2961, 85.8245)
    assert 15 < distance < 25


def test_haversine_is_zero_for_the_same_point():
    assert geo.haversine_km(20.0, 85.0, 20.0, 85.0) == pytest.approx(0.0, abs=1e-9)


def test_nearest_district_resolves_known_centroids():
    assert geo.nearest_district(20.2961, 85.8245)[0] == "Khordha"
    assert geo.nearest_district(19.8135, 85.8312)[0] == "Puri"
    assert geo.nearest_district(20.4847, 85.8649)[0] == "Cuttack"


def test_in_odisha_accepts_inside_and_rejects_outside():
    assert geo.in_odisha(20.2961, 85.8245) is True
    assert geo.in_odisha(28.6139, 77.2090) is False  # Delhi


def test_obscure_keeps_exact_coordinates_when_not_sensitive():
    assert geo.obscure_coordinates(20.4847, 85.8649, "exact", False) == (
        20.4847,
        85.8649,
        "exact",
    )


def test_obscure_snaps_sensitive_coordinates_to_a_coarse_grid():
    lat, lon, precision = geo.obscure_coordinates(20.4847, 85.8649, "exact", True)
    assert precision == "approximate"
    # ~11 km grid: every value must be a multiple of 0.1.
    assert round(lat, 1) == lat
    assert round(lon, 1) == lon
    assert (lat, lon) != (20.4847, 85.8649)


def test_obscure_snaps_approximate_coordinates_to_a_fine_grid():
    lat, lon, precision = geo.obscure_coordinates(20.4847, 85.8649, "approximate", False)
    assert precision == "approximate"
    assert round(lat, 2) == lat
    assert round(lon, 2) == lon


def test_obscure_passes_district_precision_through():
    assert geo.obscure_coordinates(20.4, 85.8, "district", False) == (20.4, 85.8, "district")


def test_plausibility_without_any_location():
    result = geo.plausibility_check("IN-OR", None, None, None)
    assert result["status"] == "not_provided"


def test_plausibility_with_district_only_skips_distance_checks():
    result = geo.plausibility_check("IN-OR", "Khordha", None, None)
    assert result["status"] == "plausible"
    assert "distance checks are skipped" in result["message"]


def test_plausibility_inside_a_known_region():
    result = geo.plausibility_check("IN-OR", None, 20.2961, 85.8245)
    assert result["status"] == "plausible"
    assert result["region_code"] == "IN-OR"


def test_plausibility_outside_odisha_is_a_review_flag_not_absence():
    result = geo.plausibility_check("IN-OR", None, 28.6139, 77.2090)
    assert result["status"] == "outside_known_range"
    assert "inconclusive" in result["message"]


def test_plausibility_without_a_curated_record_is_unavailable():
    result = geo.plausibility_check(None, None, 20.2961, 85.8245)
    assert result["status"] == "unavailable"
