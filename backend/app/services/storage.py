"""Safe storage for uploaded observation images.

Rules:
* Only JPEG/PNG/WEBP content that Pillow can decode is accepted.
* Files are re-encoded (stripping EXIF/GPS metadata) and given random names.
* The upload directory never appears in the public API response; only the
  relative path served by the /media mount is exposed.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from ..config import settings

MAX_STORED_EDGE = 1800
DISPLAY_DIR = settings.upload_dir / "observations"


def save_observation_image(image: Image.Image) -> str:
    """Persist a re-encoded JPEG and return its path relative to the upload dir."""
    now = datetime.now(timezone.utc)
    directory = DISPLAY_DIR / f"{now:%Y}" / f"{now:%m}"
    directory.mkdir(parents=True, exist_ok=True)

    stored = image.copy()
    stored.thumbnail((MAX_STORED_EDGE, MAX_STORED_EDGE), Image.Resampling.LANCZOS)
    if stored.mode not in ("RGB", "L"):
        stored = stored.convert("RGB")

    filename = f"{uuid.uuid4().hex}.jpg"
    destination = directory / filename
    stored.save(destination, format="JPEG", quality=90, optimize=True)
    return destination.relative_to(settings.upload_dir).as_posix()


def image_url(relative_path: str) -> str:
    return f"/media/{relative_path}"


def delete_observation_image(relative_path: str) -> None:
    candidate = (settings.upload_dir / relative_path).resolve()
    try:
        candidate.relative_to(settings.upload_dir.resolve())
    except ValueError:
        return  # refuse to delete outside the upload directory
    if candidate.is_file():
        candidate.unlink(missing_ok=True)
