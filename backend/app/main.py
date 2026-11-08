from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, routes
from app.api.errors import install_error_handlers
from app.catalog.bootstrap import seed_if_empty
from app.config import get_settings
from app.core.logging import log_event, request_id_var, setup_logging
from app.core.store import MemoryStore, PgStore, get_store, set_store

log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    await seed_if_empty()
    try:  # persistent store if DB schema is there, otherwise in-memory (documented in README)
        from sqlalchemy import text

        from app.db.session import get_engine

        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1 FROM builds LIMIT 1"))
        set_store(PgStore())
    except Exception as exc:
        log.warning("DB store unavailable (%s): using in-memory store", type(exc).__name__)
        if not isinstance(get_store(), MemoryStore):
            set_store(MemoryStore())
    yield


app = FastAPI(title="AI PC Configuration", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)
install_error_handlers(app)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    request_id_var.set(rid)
    t0 = time.monotonic()
    response = await call_next(request)
    response.headers["x-request-id"] = rid
    if request.url.path.startswith("/api/"):
        log_event(
            log,
            "http",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            ms=round((time.monotonic() - t0) * 1000),
        )
    return response


app.include_router(health.router, prefix="/api/v1")
app.include_router(routes.router, prefix="/api/v1")
