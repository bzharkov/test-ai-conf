import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.cache import Cache, set_cache
from app.core.store import MemoryStore, set_store
from app.llm.client import LLMResult, reset_llm, set_llm
from app.main import app

H = "/api/v1"


@pytest.fixture(autouse=True)
def _env():
    set_store(MemoryStore())
    set_cache(Cache("redis://127.0.0.1:1/0"))  # unreachable -> in-memory fallback
    set_llm(None)
    yield
    reset_llm()
    set_cache(None)


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c


async def configure(client, text="Игры в 1440p до 120 000 ₽", sid="s1"):
    r = await client.post(f"{H}/configure", json={"text": text, "session_id": sid})
    assert r.status_code == 200, r.text
    return r.json()


def parse_sse(text: str):
    events = []
    for block in text.strip().split("\n\n"):
        ev = dict(line.split(": ", 1) for line in block.split("\n") if ": " in line)
        events.append((ev["event"], json.loads(ev["data"])))
    return events


async def test_configure_without_llm_uses_fallback(client):
    d = await configure(client)
    assert any(w["code"] == "llm_unavailable" for w in d["warnings"])
    assert 2 <= len(d["builds"]) <= 3
    for b in d["builds"]:
        assert b["compat_ok"] and b["total_price"] <= 120_000
        assert b["prices_are_demo"] is True
    assert d["requirements"]["budget_rub"] == 120_000


async def test_build_detail(client):
    d = await configure(client)
    r = await client.get(f"{H}/builds/{d['builds'][0]['id']}")
    b = r.json()
    assert r.status_code == 200 and b["compatibility"]["ok"]
    assert len(b["items"]) == 8 and b["power"]["installed_psu_w"] >= b["power"]["psu_recommended_w"]
    assert {x["status"] for x in b["compatibility"]["rules"]} <= {"ok", "warning"}
    assert b["requirements"]["use_cases"]


async def test_404_and_error_shape(client):
    r = await client.get(f"{H}/builds/9999")
    assert r.status_code == 404 and r.json()["error"]["code"] == "build_not_found"
    r = await client.post(f"{H}/configure", json={"text": "x"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


async def test_replace_with_alternative_and_incompatible(client):
    d = await configure(client)
    bid = d["builds"][0]["id"]
    alts = (
        await client.get(
            f"{H}/builds/{bid}/alternatives", params={"category": "gpu", "intent": "cheaper"}
        )
    ).json()
    assert alts and all(a["compat_ok"] and a["price_delta_rub"] < 0 for a in alts)
    r = await client.post(
        f"{H}/builds/{bid}/replace",
        json={
            "category": "gpu",
            "component_id": alts[0]["component_id"],
            "extra_component_id": alts[0]["extra_component_id"],
        },
    )
    assert r.status_code == 200
    nb = r.json()["build"]
    assert nb["id"] != bid and nb["compatibility"]["ok"] and nb["label"].endswith("(изменена)")
    cpus = (
        await client.get(f"{H}/components", params={"category": "motherboard", "limit": 100})
    ).json()
    old = (await client.get(f"{H}/builds/{bid}")).json()
    sock = next(i for i in old["items"] if i["category"] == "motherboard")["specs"]["socket"]
    wrong = next(c for c in cpus if c["specs"]["socket"] != sock)
    r = await client.post(
        f"{H}/builds/{bid}/replace", json={"category": "motherboard", "component_id": wrong["id"]}
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "incompatible"


async def test_compare(client):
    d = await configure(client)
    ids = [b["id"] for b in d["builds"][:2]]
    r = await client.post(f"{H}/compare", json={"build_ids": ids})
    c = r.json()
    assert r.status_code == 200 and len(c["rows"]) == 8 and any(row["differs"] for row in c["rows"])
    r = await client.post(f"{H}/compare", json={"build_ids": ids[:1]})
    assert r.status_code == 422


async def test_components_endpoints(client):
    r = await client.get(f"{H}/components", params={"category": "gpu", "q": "4060"})
    assert r.status_code == 200 and "4060" in r.json()[0]["name"]
    cid = r.json()[0]["id"]
    assert (await client.get(f"{H}/components/{cid}")).json()["id"] == cid
    assert (await client.get(f"{H}/components/99999")).status_code == 404
    assert (await client.get(f"{H}/components", params={"category": "zzz"})).status_code == 422


async def test_history_by_session(client):
    await configure(client, sid="alice")
    await configure(client, "Офисный ПК до 40 000 ₽", sid="bob")
    h = (await client.get(f"{H}/history", params={"session_id": "alice"})).json()
    assert len(h) == 1 and h[0]["builds"]


async def test_explanation_stream_template_then_cache(client):
    d = await configure(client)
    bid = d["builds"][0]["id"]
    r = await client.get(f"{H}/builds/{bid}/explanation/stream")
    ev = parse_sse(r.text)
    assert ev[-1][0] == "done" and "Под какую задачу" in ev[-1][1]["text"]
    ev2 = parse_sse((await client.get(f"{H}/builds/{bid}/explanation/stream")).text)
    assert ev2[-1][1]["source"] == "cache"
    assert (await client.get(f"{H}/builds/{bid}")).json()["explanation"]


async def test_chat_alternatives_without_llm(client):
    d = await configure(client)
    bid = d["builds"][0]["id"]
    r = await client.post(
        f"{H}/builds/{bid}/chat",
        json={"message": "чем заменить видеокарту подешевле?", "session_id": "s1"},
    )
    ev = parse_sse(r.text)
    kinds = [e[0] for e in ev]
    assert "alternatives" in kinds and kinds[-1] == "done"
    items = next(e[1] for e in ev if e[0] == "alternatives")["items"]
    assert 1 <= len(items) <= 3 and all(i["price_delta_rub"] < 0 for i in items)
    hist = (await client.get(f"{H}/builds/{bid}/chat")).json()
    assert [m["role"] for m in hist] == ["user", "assistant"]


class ScriptedLLM:
    """Streams a hallucinated answer first, then a clean one on regeneration."""

    async def complete(self, messages, **kw):
        return LLMResult("Остаёмся на текущей видеокарте.")

    async def stream(self, messages, **kw):
        for t in ["Возьмите ", "RTX 5090 ", "для запаса."]:
            yield t


async def test_chat_with_llm_validates_and_replaces(client):
    set_llm(ScriptedLLM())
    d = await configure(client)
    bid = d["builds"][0]["id"]
    r = await client.post(f"{H}/builds/{bid}/chat", json={"message": "расскажи о сборке"})
    ev = parse_sse(r.text)
    names = [e[0] for e in ev]
    assert "replace" in names and names[-1] == "done"
    assert "5090" not in ev[-1][1]["text"]


async def test_rate_limit(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "rate_limit_per_min", 2)
    for _ in range(2):
        await client.post(f"{H}/configure", json={"text": "офис 40000", "session_id": "rl"})
    r = await client.post(f"{H}/configure", json={"text": "офис 40000", "session_id": "rl"})
    assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited"
