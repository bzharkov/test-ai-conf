"""Auto-seed an empty DB so `docker compose up` yields a working catalog."""

from __future__ import annotations

import logging

from app.catalog.db_writer import component_to_row_dict, count_components, upsert_components
from app.catalog.repository import build_seed_components_async
from app.config import get_settings
from app.db.session import get_engine, get_session_maker

log = logging.getLogger("bootstrap")


async def seed_if_empty() -> None:
    s = get_settings()
    if s.catalog_source != "seed":
        return
    try:
        get_engine()
        async with get_session_maker()() as session:
            if await count_components(session) > 0:
                return
            comps = await build_seed_components_async(s.seed_dir, s.perf_scores_path)
            ins, upd = await upsert_components(session, [component_to_row_dict(c) for c in comps])
            log.info("seeded demo catalog: %s inserted, %s updated", ins, upd)
    except Exception as exc:
        log.warning("auto-seed skipped (%s)", type(exc).__name__)
