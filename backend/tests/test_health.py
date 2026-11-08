from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_health_reports_components_without_crashing(monkeypatch):
    from app.api import health

    async def ok_db():
        return {"ok": True, "catalog_size": 0}

    async def ok_redis():
        return {"ok": True}

    monkeypatch.setattr(health, "check_db", ok_db)
    monkeypatch.setattr(health, "check_redis", ok_redis)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_health_degraded_when_db_down(monkeypatch):
    from app.api import health

    async def bad_db():
        return {"ok": False, "error": "X"}

    async def ok_redis():
        return {"ok": True}

    monkeypatch.setattr(health, "check_db", bad_db)
    monkeypatch.setattr(health, "check_redis", ok_redis)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/v1/health")
    assert r.json()["status"] == "degraded"
