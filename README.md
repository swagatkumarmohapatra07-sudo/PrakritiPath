# PrakritiPath (My Utkal Heritage)

Uncertainty-aware biodiversity identification and Odisha tourism discovery, built as a
single FastAPI backend that also serves a static HTML/CSS/JS frontend.

Nothing is fabricated: if an AI model or a data source is missing, the API reports it as
unavailable instead of inventing a result.

## Features

- **Species identification** from uploaded photos (plant + bird), CPU-only, with confidence
  and uncertainty reported honestly. Gracefully degrades when no model is installed.
- **Observation logging** with geolocation, image-quality checks, and optional Wikipedia
  enrichment.
- **Biodiversity explorer** — browse and filter seeded species records.
- **Odisha tourism discovery** — destinations, categories, map view, and itinerary planning.
- **Open-source photo galleries** — each place can show several credited Wikimedia
  Commons photographs, with a lightbox, licence links and graceful fallback art.
- **Itineraries & favourites** — saved per browser session (`X-Session-Id`).
- **Admin review console** — moderate submitted reports behind basic auth.
- **Interactive API docs** at `/docs` and `/redoc`.

## Tech stack

| Layer     | Tech                                                        |
| --------- | ----------------------------------------------------------- |
| Backend   | Python 3.12, FastAPI, SQLAlchemy 2, SQLite                   |
| AI        | PyTorch (CPU), torchvision, Pillow, NumPy                    |
| Frontend  | Vanilla HTML/CSS/JS, Leaflet, Chart.js, Lucide (vendored)    |
| Data      | Seeded JSON/JSONL + on-disk SQLite (`data/biotrace.db`)       |

## Getting started

```bash
git clone https://github.com/swagatkumarmohapatra07-sudo/PrakritiPath.git
cd PrakritiPath

python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
pip install -r requirements-ai.txt   # optional, for predictions (large download)

cp .env.example .env                 # then edit: set BIOTRACE_SECRET_KEY and ADMIN_PASSWORD
python -m uvicorn backend.app.main:app --reload
```

Open <http://127.0.0.1:8000>. The SQLite database is created and seeded automatically on
first start.

## Project layout

```
backend/
  app/
    main.py          FastAPI entry point, middleware, static mounting
    config.py        Settings loaded from .env
    database.py      SQLAlchemy engine/session, init_db
    models.py        ORM models
    schemas.py       Pydantic request/response schemas
    security.py      Admin auth helpers
    rate_limit.py    In-memory rate limiting
    seed.py          Idempotent startup seeding
    routers/         admin, biodiversity, favourites, itineraries, meta, reports, tourism
    services/        predictor, storage, geo, geocoding, image_quality
    data/            Seed data (species, tourism, categories)
  scripts/           Tourism import, model training, evaluation, migration helpers
  tests/             Pytest suite (isolated temp database)
docs/                Datasets, model training and limitations
frontend/
  *.html             Pages (home, biodiversity, destination, itinerary, map, saved, tourism)
  css/  js/  assets/ Styles, modules, self-hosted fonts
  vendor/            Leaflet, Chart.js, Lucide (checked in for offline use)
data/                SQLite DB, uploads, caches (git-ignored)
models/              AI model artifacts (git-ignored; see below)
```

## Configuration

All settings live in `.env` (see `.env.example`). Key values:

| Variable              | Purpose                                                |
| --------------------- | ------------------------------------------------------ |
| `BIOTRACE_SECRET_KEY` | Signing key — set a long random string                  |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | Admin console credentials — change the defaults |
| `DATABASE_URL`        | Defaults to `sqlite:///./data/biotrace.db`              |
| `CORS_ORIGINS`        | Only needed if hosting the frontend separately          |
| `MODEL_DIR`           | Where plant/bird model artifacts live                   |
| `MAX_UPLOAD_MB`       | Upload size cap (default 8 MB)                          |

Never commit a real `.env` — it is git-ignored.

## AI models

Trained weights (`*.pt`, `*.pth`, `*.onnx`, checkpoints) are **not** in the repo. To enable
predictions, place artifacts under `models/plant/` and `models/bird/` alongside their
`model_card.json` class-name maps. Until then the app runs fine and reports models as
"not installed".

To train one:

```bash
pip install -r requirements-ai.txt
python -m backend.scripts.train_classifier \
    --category plant --data datasets/plants --epochs 8 --output models/plant
```

See [`docs/MODEL_TRAINING.md`](docs/MODEL_TRAINING.md) for the artifact contract and
[`docs/DATASETS.md`](docs/DATASETS.md) for the seed-data schema.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

The suite runs against an isolated temporary SQLite database and upload directory, so it
never touches `data/biotrace.db`. It covers the platform endpoints, tourism filters, the
species catalogue, honest "model unavailable" behaviour, image validation, per-session
favourites and itineraries, admin auth/review flows, geo helpers and seed-data integrity.

## Docs and scripts

| Path | Purpose |
| ---- | ------- |
| `docs/DATASETS.md` | Seed-data schema, import and geocoding pipeline |
| `docs/MODEL_TRAINING.md` | Model artifact contract, training and abstention threshold |
| `docs/LIMITATIONS.md` | Scientific, data, privacy and operational limits |
| `backend/scripts/import_tourism.py` | Import/geocode `tourism_seed_*.jsonl` |
| `backend/scripts/fetch_images.py` | Fetch credited Wikimedia Commons photos per place |
| `backend/scripts/train_classifier.py` | Train a MobileNetV3 classifier for My Utkal Heritage |
| `backend/scripts/evaluate.py` | Score the image-quality heuristics on a labelled probe set |
| `backend/scripts/migrate.py` | Schema drift check and Alembic bootstrap |

## Deploying to Vercel

Vercel's Python runtime serves the whole app (API + static frontend) as one
FastAPI function. The root `index.py` file re-exports the ASGI `app`; Vercel
detects FastAPI from `requirements.txt` and requires no extra configuration.

```bash
vercel link                 # create/connect the project
vercel deploy --prod        # deploy to production
```

Set these environment variables in the Vercel project (they are required because
the function filesystem is read-only):

| Variable | Value | Why |
| -------- | ----- | --- |
| `BIOTRACE_ENV` | `production` | Marks a non-development deployment |
| `DATABASE_URL` | `sqlite:////tmp/biotrace.db` | SQLite needs a writable path |
| `UPLOAD_DIR` | `/tmp/uploads` | Uploaded photos need a writable path |
| `MODEL_DIR` | `/tmp/models` | No models are bundled; the API reports them as unavailable |
| `BIOTRACE_SECRET_KEY` | long random string | Session hashing |
| `ADMIN_PASSWORD` | strong password | Admin review console |

> **Limitation:** `/tmp` is per-instance and ephemeral on Vercel. The database is
> seeded on every cold start, so reports, favourites and uploads are not durable
> across instances. For production use, point `DATABASE_URL` at a managed
> Postgres/Neon database and move uploads to Vercel Blob.

## Notes

- External services (Nominatim, Photon, Wikipedia) are optional and free; Nominatim asks for
  a descriptive `User-Agent` and ≤ 1 request/second.
- Runtime data (`data/*.db`, uploads, caches) and Python caches are git-ignored.

## License

Academic project. Add a license before redistributing.
