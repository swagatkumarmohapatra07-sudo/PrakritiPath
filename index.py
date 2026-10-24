"""Vercel entrypoint for the BioTrace FastAPI application.

Vercel's Python runtime looks for an ASGI ``app`` in a supported entrypoint
file at the project root (``index.py``, ``app.py``, ``main.py``, ...). The
real application lives in ``backend/app/main.py``; this shim keeps the
existing layout and the local ``uvicorn backend.app.main:app`` workflow
unchanged.
"""

from backend.app.main import app

__all__ = ["app"]
