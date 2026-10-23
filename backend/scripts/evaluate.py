"""Evaluate the image-quality heuristics against a hand-labelled probe set.

``backend/app/services/image_quality.py`` decides whether an upload is usable
*before* a species prediction is attempted. This script measures how well those
heuristics agree with human labels, so the thresholds can be tuned with evidence
instead of guesswork.

Expected layout:

    datasets/quality_probe/
        usable/      photos a person can plausibly identify from
        unusable/    too dark, too blurry, too small, or unusable framing

Usage (from the project root):

    python -m backend.scripts.evaluate
    python -m backend.scripts.evaluate --probe-dir path/to/probe --json
    python -m backend.scripts.evaluate --generate-demo   # smoke test only

Exit codes: 0 when F1 meets ``--min-f1`` (default 0), 1 otherwise, 2 for setup errors.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_PROBE_DIR = PROJECT_ROOT / "datasets" / "quality_probe"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score the BioTrace image-quality heuristics against labelled photos.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--probe-dir", type=Path, default=DEFAULT_PROBE_DIR)
    parser.add_argument("--json", action="store_true", help="Print machine-readable output.")
    parser.add_argument("--min-f1", type=float, default=0.0,
                        help="Fail the run when F1 is below this value.")
    parser.add_argument("--show-errors", type=int, default=10,
                        help="How many misclassified files to list (0 hides them).")
    parser.add_argument("--generate-demo", action="store_true",
                        help="Create a small synthetic probe set that only checks the harness.")
    return parser.parse_args(argv)


def _generate_demo(directory: Path) -> None:
    """Create a tiny synthetic set. Labels are obvious by construction.

    This is a smoke test for the evaluation harness, not evidence about real
    photographs. Do not report these numbers as model quality.
    """
    import numpy as np
    from PIL import Image

    usable = directory / "usable"
    unusable = directory / "unusable"
    usable.mkdir(parents=True, exist_ok=True)
    unusable.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(7)
    for index in range(4):
        noise = rng.integers(0, 256, size=(480, 640, 3), dtype=np.uint8)
        Image.fromarray(noise).save(usable / f"synthetic_texture_{index}.jpg", quality=92)

    Image.new("RGB", (480, 640), (10, 10, 10)).save(unusable / "synthetic_dark.jpg")
    Image.new("RGB", (480, 640), (128, 128, 128)).save(unusable / "synthetic_flat.jpg")
    Image.new("RGB", (64, 64), (200, 200, 200)).save(unusable / "synthetic_tiny.png")


def _collect(directory: Path) -> list[tuple[Path, bool]]:
    samples: list[tuple[Path, bool]] = []
    for folder, label in (("usable", True), ("unusable", False)):
        root = directory / folder
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
                samples.append((path, label))
    return samples


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    from backend.app.services.image_quality import assess_quality, load_and_validate

    probe_dir: Path = args.probe_dir
    if args.generate_demo:
        _generate_demo(probe_dir)
        print(f"Generated a synthetic probe set in {probe_dir} (smoke test only).\n")

    if not probe_dir.is_dir():
        print(
            f"Probe directory not found: {probe_dir}\n"
            "Create usable/ and unusable/ sub-directories of labelled photos, or run "
            "with --generate-demo for a harness smoke test.",
            file=sys.stderr,
        )
        return 2

    samples = _collect(probe_dir)
    if not samples:
        print(f"No images found under {probe_dir}.", file=sys.stderr)
        return 2

    tp = fp = tn = fn = unreadable = 0
    errors: list[dict[str, object]] = []
    issue_counts: dict[str, int] = {}

    for path, actually_usable in samples:
        try:
            image = load_and_validate(path.read_bytes())
        except Exception as exc:  # noqa: BLE001 - report, never crash the run
            unreadable += 1
            errors.append({"file": str(path), "error": str(exc), "label": actually_usable})
            continue

        result = assess_quality(image)
        predicted_usable = result.usable
        for issue in result.issues:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1

        if actually_usable and predicted_usable:
            tp += 1
        elif actually_usable and not predicted_usable:
            fn += 1
            errors.append(
                {"file": str(path), "label": "usable", "predicted": "rejected",
                 "issues": result.issues}
            )
        elif not actually_usable and predicted_usable:
            fp += 1
            errors.append(
                {"file": str(path), "label": "unusable", "predicted": "accepted",
                 "issues": result.issues}
            )
        else:
            tn += 1

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) else 0.0

    summary = {
        "probe_dir": str(probe_dir),
        "samples": len(samples),
        "unreadable": unreadable,
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "issue_counts": issue_counts,
        "errors": errors,
        "note": (
            "Recall is the share of human-usable photos the checks accepted. "
            "Low recall means good photos are being rejected; high false positives "
            "mean unusable photos reach the model."
        ),
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"Probe set: {probe_dir}  ({len(samples)} images, {unreadable} unreadable)")
        print(f"  usable accepted (TP) : {tp}")
        print(f"  usable rejected (FN) : {fn}")
        print(f"  unusable rejected(TN): {tn}")
        print(f"  unusable accepted(FP): {fp}")
        print(f"  precision={precision:.3f}  recall={recall:.3f}  F1={f1:.3f}  accuracy={accuracy:.3f}")
        if issue_counts:
            top = ", ".join(f"{k}={v}" for k, v in sorted(issue_counts.items(), key=lambda x: -x[1]))
            print(f"  issues raised        : {top}")
        if errors and args.show_errors:
            print("\nMisclassified:")
            for item in errors[: args.show_errors]:
                print(f"  - {item}")

    return 0 if f1 >= args.min_f1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
