"""A tiny in-process rate limiter.

This is intentionally dependency-free. It protects the expensive upload and
inference endpoints on a single-process academic deployment. For production,
swap it for a Redis-backed limiter (see docs/LIMITATIONS.md).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                retry_after = max(1, int(self.window - (now - hits[0])))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Too many requests. Please wait {retry_after} seconds and try again."
                    ),
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def client_key(request: Request, suffix: str = "") -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}:{suffix}"


upload_limiter = SlidingWindowLimiter(limit=10, window_seconds=60)
auth_limiter = SlidingWindowLimiter(limit=8, window_seconds=300)
write_limiter = SlidingWindowLimiter(limit=30, window_seconds=60)
