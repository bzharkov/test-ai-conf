"""Load the bundled demo catalog (no network needed). Idempotent."""

import asyncio

import _common  # noqa: F401

from app.catalog.db_writer import component_to_row_dict, upsert_components
from app.catalog.repository import build_seed_components_async
from app.config import get_settings
from app.db.session import get_engine, get_session_maker


async def main() -> None:
    s = get_settings()
    comps = await build_seed_components_async(s.seed_dir, s.perf_scores_path)
    get_engine()
    async with get_session_maker()() as session:
        ins, upd = await upsert_components(session, [component_to_row_dict(c) for c in comps])
    print(f"demo catalog: {ins} inserted, {upd} updated, {len(comps)} total")


if __name__ == "__main__":
    asyncio.run(main())
