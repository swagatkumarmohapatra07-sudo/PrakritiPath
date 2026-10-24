# Limitations

BioTrace is an academic project. It is designed to be **honest about what it cannot
do**, but the honesty is only useful if the limits are written down.

## Scientific limitations

- **Small demonstration models.** Any bundled or example classifier is trained on a
  small dataset. It does not cover all Odisha flora or avifauna.
- **Confidence is not correctness.** `confidence_score` is the model's softmax score
  for its chosen label, not the probability that the identification is right.
- **Look-alikes fail.** Juveniles, hybrids, damaged specimens, non-flowering plants and
  distant or silhouetted birds are common failure cases.
- **Distribution data is coarse.** `known_regions` is recorded at Odisha level
  (`IN-OR`). A location outside a curated range is a **review flag**, never proof of
  absence.
- **Nothing is auto-verified.** Every observation starts as `pending`; a human must
  review it before it counts as a record.

## Data limitations

- Tourism facts (opening hours, entry fees, contact details) are often `null`. The UI
  shows "Not verified" rather than guessing.
- Coordinates come from OpenStreetMap/Nominatim and may be approximate or wrong.
- District centroids in `backend/app/services/geo.py` are approximate administrative
  points, not survey data. They are used only to suggest a district.
- There is no live traffic, weather, crowd or route-optimisation data.

## Image handling

- Uploads must be JPEG, PNG or WEBP, at most 64×64 minimum and `MAX_UPLOAD_MB` (8 MB
  by default) maximum.
- Images are re-encoded on save, which strips EXIF/GPS metadata.
- The quality check is a set of transparent heuristics (brightness, contrast, Laplacian
  sharpness). It will occasionally reject a usable photo or accept a poor one.

## Privacy

- Anonymous visitors get a random session id in `localStorage`. It is hashed with
  `BIOTRACE_SECRET_KEY` before storage; itineraries, favourites and reports are scoped
  to that hash.
- Observations are only stored when the uploader ticks consent. Un-consented records
  are hidden from public endpoints.
- Sensitive records (threatened species) have coordinates snapped to a ~11 km grid by
  the public API.
- There is no user account system and no third-party analytics.

## Photographs

- Destination photos come from **Wikimedia Commons** and are reused under their own
  free licences (CC0, public domain, CC BY, CC BY-SA). Each photo is credited in the
  gallery and links to its file page; that attribution must not be removed if the
  images are reused elsewhere.
- Images are hot-linked from `upload.wikimedia.org`, so they need network access.
  When a photo fails to load the UI falls back to generated category artwork.
- A photo shows the place as a contributor photographed it, possibly years ago and
  possibly from an angle that hides current conditions. It is illustrative, not a
  guarantee of what a visitor will see.
- Places with no suitable free photograph are left without images rather than being
  filled with an unrelated or non-free picture.

## Operational limitations

- **Single process.** Rate limiting is an in-memory sliding window
  (`backend/app/rate_limit.py`). Multiple workers each get their own counters. Use a
  Redis-backed limiter for a real deployment.
- **SQLite.** Fine for a demo and a single reviewer, not for concurrent heavy writes.
  `init_db()` uses `create_all` rather than migrations — see
  `backend/scripts/migrate.py` if you need Alembic.
- **No background jobs.** Imports and geocoding run as CLI scripts, not workers.
- **Admin auth is basic.** One account from `ADMIN_USERNAME`/`ADMIN_PASSWORD`, a
  signed HMAC bearer token, no password reset, no MFA, no audit UI beyond the review
  log table.
- **Insecure defaults.** The default admin password and secret key are placeholders.
  Set both in `.env` before exposing the app to anyone.

## Frontend

- Vanilla JavaScript, no build step, no framework. Browser support targets current
  Chrome, Firefox, Safari and Edge.
- Leaflet tiles and fonts are self-hosted/vendored for offline use; base map tiles
  still require network access to OpenStreetMap.
- Accessibility is best-effort (semantic landmarks, labels, focus styles) and has not
  been audited against WCAG.

## What this project deliberately does not do

- It does not claim a species identification is confirmed.
- It does not invent tourism facts, coordinates or contact details.
- It does not silently accept a low-confidence prediction.
- It does not train on or redistribute data whose licence forbids it.
