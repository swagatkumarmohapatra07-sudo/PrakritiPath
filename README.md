# PrakritiPath (BioTrace)

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
  scripts/           Tourism import + geocoding CLIs
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

## Notes

- External services (Nominatim, Photon, Wikipedia) are optional and free; Nominatim asks for
  a descriptive `User-Agent` and ≤ 1 request/second.
- Runtime data (`data/*.db`, uploads, caches) and Python caches are git-ignored.

## License

Academic project. Add a license before redistributing.
