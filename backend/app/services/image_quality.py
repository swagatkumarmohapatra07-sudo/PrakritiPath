"""Image validation and quality assessment.

The checks are transparent heuristics, not guarantees. They flag images that a
human would probably find difficult to identify from, and they are evaluated in
``scripts/evaluate.py`` against a small hand-labelled quality probe set.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MIN_DIMENSION = 160


@dataclass
class ImageQuality:
    status: str  # good | warning | poor
    usable: bool
    width: int | None = None
    height: int | None = None
    brightness: float | None = None
    sharpness: float | None = None
    issues: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "usable": self.usable,
            "width": self.width,
            "height": self.height,
            "brightness": self.brightness,
            "sharpness": self.sharpness,
            "issues": self.issues,
            "notes": self.notes,
        }


class ImageValidationError(ValueError):
    """Raised when an upload is not a readable, permitted image."""


def load_and_validate(raw: bytes) -> Image.Image:
    if not raw:
        raise ImageValidationError("The uploaded file is empty.")
    try:
        probe = Image.open(io.BytesIO(raw))
        probe.verify()
        # Re-open after verify(): Pillow invalidates the file object.
        image = Image.open(io.BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageValidationError(
            "The file is not a readable image. Please upload a JPEG, PNG or WEBP photo."
        ) from exc

    if image.format not in ALLOWED_FORMATS:
        raise ImageValidationError(
            f"Unsupported image format '{image.format}'. Use JPEG, PNG or WEBP."
        )
    if image.width < 64 or image.height < 64:
        raise ImageValidationError("The image is too small to analyse (minimum 64×64 pixels).")
    if image.width * image.height > 40_000_000:
        raise ImageValidationError("The image resolution is too large (over 40 megapixels).")
    return ImageOps.exif_transpose(image).convert("RGB")


def assess_quality(image: Image.Image) -> ImageQuality:
    """Compute brightness, contrast and sharpness heuristics."""
    small = image.copy()
    small.thumbnail((512, 512))
    gray = np.asarray(small.convert("L"), dtype=np.float32)

    brightness = float(gray.mean())
    contrast = float(gray.std())

    # Sharpness: mean absolute Laplacian response (a common lightweight proxy).
    laplacian = (
        -4 * gray[1:-1, 1:-1]
        + gray[:-2, 1:-1]
        + gray[2:, 1:-1]
        + gray[1:-1, :-2]
        + gray[1:-1, 2:]
    )
    sharpness = float(np.abs(laplacian).mean())

    issues: list[str] = []
    notes: list[str] = []

    if min(image.width, image.height) < MIN_DIMENSION:
        issues.append("low_resolution")
        notes.append(
            f"Image is only {image.width}×{image.height}px. Fine detail used for "
            "species identification may be missing."
        )
    if brightness < 45:
        issues.append("too_dark")
        notes.append("Image is very dark; colour and texture cues are unreliable.")
    elif brightness > 225:
        issues.append("overexposed")
        notes.append("Image is very bright or washed out; detail may be lost.")
    if contrast < 18:
        issues.append("low_contrast")
        notes.append("Low contrast: the subject may not stand out from the background.")
    if sharpness < 6:
        issues.append("blurry")
        notes.append(
            "Low edge detail detected. The photo may be blurry, out of focus, or "
            "lack a close view of the subject."
        )

    hard_fail = {"too_dark", "blurry", "low_resolution"}
    if hard_fail & set(issues):
        status, usable = "poor", False
    elif issues:
        status, usable = "warning", True
    else:
        status, usable = "good", True

    if not issues:
        notes.append("Basic quality checks passed. This does not guarantee a correct ID.")

    return ImageQuality(
        status=status,
        usable=usable,
        width=image.width,
        height=image.height,
        brightness=round(brightness, 1),
        sharpness=round(sharpness, 2),
        issues=issues,
        notes=notes,
    )
