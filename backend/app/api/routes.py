from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.api.errors import ApiError
from app.api.serializers import build_out, component_out, summary
from app.catalog.repository import get_catalog
from app.compat import check_build
from app.config import get_settings
from app.core.builds import BuildView, hydrate, stored_from_build, to_stored
from app.core.cache import get_cache
from app.core.logging import log_event
from app.core.store import get_store
from app.domain import CATEGORIES, CATEGORY_RU
from app.llm.chat import alt_to_dict, chat_events
from app.llm.client import get_llm
from app.llm.explain import explanation_events
from app.llm.parser import parse_requirements
from app.llm.schemas import Requirements
from app.rag.alternatives import find_alternatives
from app.recommender.service import recommend
from app.schemas.api import (
    AlternativeOut,
    BuildOut,
    ChatMessageOut,
    ChatRequest,
    CompareCell,
    CompareRequest,
    CompareResponse,
    CompareRow,
    ComponentOut,
    ConfigureRequest,
    ConfigureResponse,
    HistoryItem,
    ReplaceRequest,
    ReplaceResponse,
)

log = logging.getLogger("api")
router = APIRouter()


async def _rate_limit(kind: str, key: str) -> None:
    n = await get_cache().hit(f"{kind}:{key}", 60)
    if n > get_settings().rate_limit_per_min:
        raise ApiError(429, "rate_limited", "Слишком много запросов, попробуйте через минуту.")


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _load_view(build_id: int) -> tuple[BuildView, dict | None]:
    store, catalog = get_store(), await get_catalog()
    stored = await store.get_build(build_id)
    if stored is None:
        raise ApiError(404, "build_not_found", "Сборка не найдена")
    view = hydrate(stored, catalog)
    req = None
    if view.request_id:
        r = await store.get_request(view.request_id)
        req = r["parsed_requirements"] if r else None
    return view, req


@router.post("/configure", response_model=ConfigureResponse)
async def configure(body: ConfigureRequest) -> ConfigureResponse:
    await _rate_limit("configure", body.session_id)
    t0 = time.monotonic()
    catalog, store = await get_catalog(), get_store()
    warnings: list[dict] = []
    if body.requirements is not None:
        req = body.requirements
    else:
        req, warnings = await parse_requirements(body.text, get_llm(), get_cache(), body.filters)
    t_parse = time.monotonic()
    result = await asyncio.to_thread(recommend, catalog, req)
    t_rec = time.monotonic()
    warnings += result.warnings
    request_id = await store.save_request(
        body.session_id, body.text, result.requirements.model_dump()
    )
    summaries = []
    for rec in result.recs:
        bid = await store.save_build(to_stored(rec, request_id, result.budget))
        stored = await store.get_build(bid)
        assert stored is not None
        summaries.append(summary(hydrate(stored, catalog)))
    log_event(
        log,
        "configure.done",
        parse_s=round(t_parse - t0, 3),
        recommend_s=round(t_rec - t_parse, 3),
        builds=len(summaries),
        budget=result.budget,
        over_budget=result.min_feasible_price is not None,
    )
    return ConfigureResponse(
        request_id=request_id,
        requirements=result.requirements,
        builds=summaries,
        warnings=warnings,  # type: ignore[arg-type]
        min_feasible_price=result.min_feasible_price,
    )


@router.get("/builds/{build_id}", response_model=BuildOut)
async def get_build(build_id: int) -> BuildOut:
    view, req = await _load_view(build_id)
    return build_out(view, Requirements.model_validate(req) if req else None)


@router.get("/builds/{build_id}/explanation/stream")
async def explanation_stream(build_id: int) -> StreamingResponse:
    view, req = await _load_view(build_id)
    catalog, store = await get_catalog(), get_store()

    async def gen() -> AsyncIterator[str]:
        if view.explanation:
            text = view.explanation
            for i in range(0, len(text), 80):
                yield sse("token", {"text": text[i : i + 80]})
            yield sse("done", {"text": text, "source": "cache"})
            return
        try:
            async for ev in explanation_events(view, req, catalog, get_llm()):
                if ev["event"] == "done":
                    await store.set_explanation(build_id, ev["data"]["text"])
                yield sse(ev["event"], ev["data"])
        except Exception as exc:
            log_event(log, "explanation.error", error=type(exc).__name__)
            yield sse("error", {"message": "Не удалось сформировать объяснение"})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/builds/{build_id}/replace", response_model=ReplaceResponse)
async def replace(build_id: int, body: ReplaceRequest) -> ReplaceResponse:
    view, req = await _load_view(build_id)
    catalog, store = await get_catalog(), get_store()
    comp = catalog.get(body.component_id)
    if comp is None or comp.category != body.category or not comp.purchasable:
        raise ApiError(404, "component_not_found", "Комплектующее не найдено или нет в наличии")
    old = (
        view.build.storage[0]
        if body.category == "storage" and view.build.storage
        else getattr(view.build, body.category, None)
    )
    nb = view.build.with_component(comp)
    if body.extra_component_id is not None:
        extra = catalog.get(body.extra_component_id)
        if extra is None or not extra.purchasable:
            raise ApiError(404, "component_not_found", "Дополнительный компонент не найден")
        nb = nb.with_component(extra)
    issues = check_build(nb)
    errors = [i for i in issues if i.severity == "error"]
    if errors:
        raise ApiError(
            409,
            "incompatible",
            "Замена несовместима со сборкой: " + "; ".join(i.message_ru for i in errors),
            {"issues": [i.as_dict() for i in errors]},
        )
    warns = [
        {"code": i.code, "message_ru": i.message_ru} for i in issues if i.severity == "warning"
    ]
    label = view.label if view.label.endswith("(изменена)") else f"{view.label} (изменена)"
    stored = stored_from_build(nb, label, view.request_id, view.budget, view.score, warns)
    new_id = await store.save_build(stored)
    new_view, _ = await _load_view(new_id)
    return ReplaceResponse(
        build=build_out(new_view, Requirements.model_validate(req) if req else None),
        replaced={
            "category": body.category,
            "from": old.name if old else None,
            "to": comp.name,
            "old_build_id": build_id,
        },
    )


@router.get("/builds/{build_id}/alternatives", response_model=list[AlternativeOut])
async def alternatives(
    build_id: int,
    category: str = Query(...),
    intent: str = Query("similar", pattern="^(cheaper|better|similar)$"),
    k: int = Query(3, ge=1, le=6),
) -> list[AlternativeOut]:
    if category not in CATEGORIES:
        raise ApiError(422, "validation_error", f"Неизвестная категория: {category}")
    view, _ = await _load_view(build_id)
    catalog = await get_catalog()
    alts = await asyncio.to_thread(find_alternatives, catalog, view.build, category, intent, k)
    return [AlternativeOut(**alt_to_dict(a)) for a in alts]


@router.post("/builds/{build_id}/chat")
async def chat(build_id: int, body: ChatRequest, request: Request) -> StreamingResponse:
    key = body.session_id or (request.client.host if request.client else "anon")
    await _rate_limit("chat", key)
    view, req = await _load_view(build_id)
    catalog, store = await get_catalog(), get_store()

    async def gen() -> AsyncIterator[str]:
        try:
            async for ev in chat_events(view, req, body.message, catalog, get_llm(), store):
                yield sse(ev["event"], ev["data"])
        except Exception as exc:
            log_event(log, "chat.error", error=type(exc).__name__)
            yield sse("error", {"message": "Не удалось получить ответ, попробуйте ещё раз"})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/builds/{build_id}/chat", response_model=list[ChatMessageOut])
async def chat_history(build_id: int) -> list[ChatMessageOut]:
    await _load_view(build_id)
    return [ChatMessageOut(**m) for m in await get_store().get_chat(build_id)]


@router.post("/compare", response_model=CompareResponse)
async def compare(body: CompareRequest) -> CompareResponse:
    views = [(await _load_view(i))[0] for i in body.build_ids]
    rows = []
    for cat in CATEGORIES:
        cells = []
        for v in views:
            c = (
                v.build.storage[0]
                if cat == "storage" and v.build.storage
                else (getattr(v.build, cat, None) if cat != "storage" else None)
            )
            cells.append(
                CompareCell(name=c.name if c else None, price_rub=c.price_rub if c else None)
            )
        rows.append(
            CompareRow(
                category=cat,
                category_ru=CATEGORY_RU[cat],
                cells=cells,
                differs=len({c.name for c in cells}) > 1,
            )
        )
    return CompareResponse(
        builds=[summary(v) for v in views],
        rows=rows,
        totals=[round(v.total) for v in views],
        power_w=[round(v.power.estimated_power_w) for v in views],
    )


@router.get("/components", response_model=list[ComponentOut])
async def components(
    category: str | None = None, q: str | None = None, limit: int = Query(20, ge=1, le=100)
) -> list[ComponentOut]:
    if category and category not in CATEGORIES:
        raise ApiError(422, "validation_error", f"Неизвестная категория: {category}")
    catalog = await get_catalog()
    return [component_out(c) for c in catalog.search(q, category, limit)]


@router.get("/components/{component_id}", response_model=ComponentOut)
async def component(component_id: int) -> ComponentOut:
    c = (await get_catalog()).get(component_id)
    if c is None:
        raise ApiError(404, "component_not_found", "Комплектующее не найдено")
    return component_out(c)


@router.get("/history", response_model=list[HistoryItem])
async def history(session_id: str = Query(..., min_length=1, max_length=64)) -> list[HistoryItem]:
    return [HistoryItem(**h) for h in await get_store().history(session_id)]
