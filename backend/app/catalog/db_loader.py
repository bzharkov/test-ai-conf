from __future__ import annotations

from sqlalchemy import select

from app.db.models import ComponentRow
from app.db.session import get_engine, get_session_maker
from app.domain import Component


async def load_db_components() -> list[Component]:
    get_engine()
    maker = get_session_maker()
    async with maker() as session:
        rows = (await session.execute(select(ComponentRow).order_by(ComponentRow.id))).scalars()
        out = []
        for r in rows:
            emb = tuple(float(x) for x in r.embedding) if r.embedding is not None else None
            out.append(
                Component(
                    id=r.id,
                    category=r.category,
                    brand=r.brand,
                    model=r.model,
                    name=r.name,
                    specs=dict(r.specs),
                    perf_score=r.perf_score,
                    perf_multicore=r.perf_multicore,
                    perf_estimated=bool(r.perf_estimated),
                    price_rub=float(r.price_rub) if r.price_rub is not None else None,
                    in_stock=bool(r.in_stock),
                    price_source=r.price_source,
                    price_updated_at=r.price_updated_at.date().isoformat()
                    if r.price_updated_at
                    else None,
                    source=r.source,
                    source_ref=r.source_ref,
                    embedding=emb,
                )
            )
        return out
