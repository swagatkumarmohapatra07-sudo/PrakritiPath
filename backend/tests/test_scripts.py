"""Unit tests for the helper scripts (no torch or network required)."""

from __future__ import annotations

import io

from PIL import Image

from backend.scripts import evaluate, migrate, train_classifier


# --------------------------------------------------------------------------- #
# train_classifier metrics
# --------------------------------------------------------------------------- #
def test_macro_f1_is_one_for_a_perfect_prediction():
    truth = [0, 1, 2, 0, 1, 2]
    assert train_classifier._macro_f1(truth, truth, 3) == 1.0


def test_macro_f1_penalises_a_collapsed_prediction():
    truth = [0, 1, 2, 0, 1, 2]
    predicted = [0, 0, 0, 0, 0, 0]
    score = train_classifier._macro_f1(truth, predicted, 3)
    assert 0.0 < score < 0.5


def test_macro_f1_ignores_absent_classes():
    # If only class 0 is present, the result is class 0's own F1.
    assert train_classifier._macro_f1([0, 0], [0, 0], 3) == 1.0


def test_threshold_selection_respects_the_error_budget():
    confidences = [0.9, 0.92, 0.4, 0.45, 0.95]
    correct = [True, True, False, False, True]
    threshold, coverage, error_rate = train_classifier._choose_threshold(
        confidences, correct, max_error=0.10
    )
    # 0.50 is the lowest cut-off that excludes both wrong, low-confidence answers.
    assert threshold == 0.5
    assert coverage == 3 / 5
    assert error_rate == 0.0


def test_threshold_selection_falls_back_when_every_bucket_is_noisy():
    confidences = [0.31, 0.32, 0.33]
    correct = [False, False, False]
    threshold, coverage, error_rate = train_classifier._choose_threshold(
        confidences, correct, max_error=0.0
    )
    assert 0.3 <= threshold <= 0.95
    assert coverage > 0
    assert error_rate == 1.0


# --------------------------------------------------------------------------- #
# evaluate probe collection
# --------------------------------------------------------------------------- #
def _write_image(path, colour):
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), colour).save(buffer, format="PNG")
    path.write_bytes(buffer.getvalue())


def test_collect_labels_images_by_folder(tmp_path):
    _write_image(tmp_path / "usable" / "a.png", (10, 200, 10))
    _write_image(tmp_path / "unusable" / "b.png", (10, 10, 10))
    (tmp_path / "usable" / "notes.txt").write_text("ignored", encoding="utf-8")

    samples = evaluate._collect(tmp_path)
    by_name = {path.name: label for path, label in samples}

    assert by_name == {"a.png": True, "b.png": False}


def test_collect_returns_nothing_for_an_empty_directory(tmp_path):
    assert evaluate._collect(tmp_path) == []


def test_generated_demo_probe_has_both_labels(tmp_path):
    evaluate._generate_demo(tmp_path)
    samples = evaluate._collect(tmp_path)
    labels = {label for _, label in samples}
    assert labels == {True, False}


# --------------------------------------------------------------------------- #
# migrate schema check
# --------------------------------------------------------------------------- #
def test_schema_check_passes_for_the_test_database():
    # The autouse fixture created every model table, so there is no drift.
    assert migrate.check() == 0
