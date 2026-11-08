from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.text import make_search_text
from app.db.models import ComponentRow
from app.domain import Component


def _row(d: dict[str, Any]) -> dict[str, Any]:
    pa = d.get("price_updated_at")
    if isinstance(pa, str) and pa:
        pa = datetime.fromisoformat(pa)
    return {
        "category": d["category"],
        "brand": d["brand"],
        "model": d["model"],
        "name": d["name"],
        "specs": d["specs"],
        "perf_score": d.get("perf_score"),
        "perf_multicore": d.get("perf_multicore"),
        "perf_estimated": bool(d.get("perf_estimated", False)),
        "price_rub": d.get("price_rub"),
        "in_stock": bool(d.get("in_stock", False)),
        "price_source": d.get("price_source"),
        "price_updated_at": pa or None,
        "source": d["source"],
        "source_ref": d.get("source_ref"),
        "search_text": make_search_text(d["category"], d["brand"], d["model"], d["specs"]),
    }


async def upsert_components(session: AsyncSession, rows: list[dict[str, Any]]) -> tuple[int, int]:
    """Idempotent upsert keyed by (category, brand, model). Returns (inserted, updated)."""
    inserted = updated = 0
    for d in rows:
        values = _row(d)
        existing = (
            await session.execute(
                select(ComponentRow.id).where(
                    ComponentRow.category == values["category"],
                    ComponentRow.brand == values["brand"],
                    ComponentRow.model == values["model"],
                )
            )
        ).scalar_one_or_none()
        stmt = insert(ComponentRow).values(**values)
        update_cols = {k: v for k, v in values.items() if k not in ("category", "brand", "model")}
        if values["price_rub"] is None:  # do not wipe prices on a re-import without prices
            for k in ("price_rub", "in_stock", "price_source", "price_updated_at"):
                update_cols.pop(k)
        stmt = stmt.on_conflict_do_update(constraint="uq_component_identity", set_=update_cols)
        await session.execute(stmt)
        if existing is None:
            inserted += 1
        else:
            updated += 1
    await session.commit()
    return inserted, updated


def component_to_row_dict(c: Component) -> dict[str, Any]:
    return {
        "category": c.category,
        "brand": c.brand,
        "model": c.model,
        "name": c.name,
        "specs": c.specs,
        "perf_score": c.perf_score,
        "perf_multicore": c.perf_multicore,
        "perf_estimated": c.perf_estimated,
        "price_rub": c.price_rub,
        "in_stock": c.in_stock,
        "price_source": c.price_source,
        "price_updated_at": c.price_updated_at,
        "source": c.source,
        "source_ref": c.source_ref,
    }


async def count_components(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(ComponentRow))).scalar_one()


async def apply_prices(session: AsyncSession, prices: dict[int, Any]) -> int:
    n = 0
    for cid, p in prices.items():
        await session.execute(
            update(ComponentRow)
            .where(ComponentRow.id == cid)
            .values(
                price_rub=p.price_rub,
                in_stock=p.in_stock,
                price_source=p.source,
                price_updated_at=datetime.fromisoformat(p.updated_at) if p.updated_at else None,
            )
        )
        n += 1
    await session.commit()
    return n


async def ensure_vector_extension(session: AsyncSession) -> None:
    await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
