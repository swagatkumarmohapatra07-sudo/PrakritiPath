"""BioTrace FastAPI application entry point.

Run from the project root:
    python -m uvicorn backend.app.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import FRONTEND_DIR, settings
from .database import SessionLocal, init_db
from .routers import admin, biodiversity, favourites, itineraries, meta, reports, tourism
from .seed import seed_all
from .services.predictor import registry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("biotrace")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        summary = seed_all(db, settings.admin_username, settings.admin_password)
        if any(summary.values()):
            logger.info("Seeded database: %s", summary)
    except Exception:  # noqa: BLE001 - never block startup on seeding
        logger.exception("Database seeding failed; check data files and permissions.")
    finally:
        db.close()

    status = registry.status()
    logger.info(
        "AI models — plant: %s, bird: %s",
        "ready" if status["plant"]["available"] else "not installed",
        "ready" if status["bird"]["available"] else "not installed",
    )
    if settings.admin_password in {"change-me-please", "admin"}:
        logger.warning(
            "ADMIN_PASSWORD is using an insecure default. Set it in .env before sharing the app."
        )
    yield


app = FastAPI(
    title="BioTrace API",
    version="1.0.0",
    description=(
        "Uncertainty-aware biodiversity identification and Odisha tourism discovery. "
        "Interactive docs: /docs. Model availability and data provenance are exposed "
        "honestly; nothing is fabricated when a model or source is missing."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-Session-Id", "Authorization"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data: blob: https://*.tile.openstreetmap.org "
        "https://unpkg.com; style-src 'self' 'unsafe-inline'; script-src 'self'; "
        "font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'",
    )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": (
                "Something went wrong on the server. The error was logged. "
                "If this persists, check the terminal running BioTrace."
            )
        },
    )


api_routers = [
    meta.router,
    tourism.router,
    biodiversity.router,
    favourites.router,
    itineraries.router,
    reports.router,
    admin.router,
]
for api_router in api_routers:
    app.include_router(api_router)

# Uploaded observation images (re-encoded, EXIF stripped). Mounted read-only.
app.mount("/media", StaticFiles(directory=settings.upload_dir, check_dir=False), name="media")

# The frontend is a set of static pages served by the same origin as the API.
# html=True makes / resolve to index.html and gives clean page URLs.
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
else:  # pragma: no cover - only before the frontend exists
    @app.get("/")
    def missing_frontend():
        return {"detail": "Frontend directory not found. See README.md."}
