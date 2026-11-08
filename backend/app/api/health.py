import asyncio
from typing import Any

from fastapi import APIRouter
from redis.asyncio import Redis
from sqlalchemy import text

from app.config import get_settings
from app.db.session import get_engine

router = APIRouter()


async def check_db() -> dict[str, Any]:
    try:
        async with get_engine().connect() as conn:
            await asyncio.wait_for(conn.execute(text("SELECT 1")), timeout=3)
            try:
                n = (await conn.execute(text("SELECT count(*) FROM components"))).scalar_one()
            except Exception:  # table appears in stage 2
                n = None
        return {"ok": True, "catalog_size": n}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}


async def check_redis() -> dict[str, Any]:
    client = Redis.from_url(get_settings().redis_url)
    try:
        await asyncio.wait_for(client.ping(), timeout=3)
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}
    finally:
        await client.aclose()


@router.get("/health")
async def health() -> dict[str, Any]:
    s = get_settings()
    db, redis = await asyncio.gather(check_db(), check_redis())
    llm = {"ok": s.llm_available, "enabled": s.llm_enabled, "configured": s.llm_available}
    # LLM is optional (fallback parser exists), so it does not affect overall status.
    status = "ok" if db["ok"] and redis["ok"] else "degraded"
    from app.catalog.repository import get_catalog

    size: int | None
    source: str | None
    try:
        cat = await get_catalog()
        size, source = len(cat), cat.mode
    except Exception:
        size, source = db.get("catalog_size"), None
    return {
        "status": status,
        "db": db,
        "redis": redis,
        "llm": llm,
        "catalog_size": size,
        "catalog_source": source,
    }
