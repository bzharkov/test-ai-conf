"""Compute search_text embeddings (e5-small, CPU) and store them in components.embedding."""

import asyncio

import _common  # noqa: F401
from sqlalchemy import select, update

from app.catalog.text import make_search_text
from app.db.models import ComponentRow
from app.db.session import get_engine, get_session_maker
from app.rag.embeddings import get_embedder


async def main(batch: int = 64) -> None:
    emb = get_embedder()
    get_engine()
    async with get_session_maker()() as session:
        rows = (
            await session.execute(
                select(
                    ComponentRow.id,
                    ComponentRow.category,
                    ComponentRow.brand,
                    ComponentRow.model,
                    ComponentRow.specs,
                    ComponentRow.search_text,
                ).order_by(ComponentRow.id)
            )
        ).all()
        for i in range(0, len(rows), batch):
            chunk = rows[i : i + batch]
            texts = [
                r.search_text or make_search_text(r.category, r.brand, r.model, r.specs)
                for r in chunk
            ]
            vecs = await asyncio.to_thread(emb.embed_passages, texts)
            for r, t, v in zip(chunk, texts, vecs, strict=True):
                await session.execute(
                    update(ComponentRow)
                    .where(ComponentRow.id == r.id)
                    .values(embedding=v, search_text=t)
                )
            await session.commit()
            print(f"embedded {min(i + batch, len(rows))}/{len(rows)} with {emb.name}")


if __name__ == "__main__":
    asyncio.run(main())
