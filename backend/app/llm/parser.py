"""Request -> Requirements: LLM with schema + retries, merged with the regex parser (TZ 8.1)."""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from pydantic import ValidationError

from app.core.cache import Cache
from app.core.logging import log_event
from app.llm.client import LLMClient, extract_json
from app.llm.fallback_parser import parse_requirements_fallback
from app.llm.schemas import Requirements

log = logging.getLogger("parser")
MAX_RETRIES = 2
CACHE_TTL_S = 24 * 3600

SYSTEM = (
    "Ты разбираешь запрос пользователя на подбор ПК и возвращаешь СТРОГО один JSON-объект без "
    "пояснений. Поля: use_cases (список из gaming, office, video_editing, 3d_render, programming, "
    "study, streaming, ml), primary_use_case, budget_rub (целое число в рублях или null), "
    "budget_is_strict (bool), gaming ({resolution: 1080p|1440p|4k|null, target_fps, titles[]} или "
    "null), preferences ({cpu_brand: amd|intel|any, gpu_brand: amd|nvidia|intel|any, form_factor: "
    "any|compact|mini_itx, wifi_required, min_ram_gb, min_storage_gb, quiet, rgb, "
    "no_discrete_gpu}), must_include (явно названные модели), exclude, notes, confidence (0..1). "
    "Не выдумывай бюджет, если он не назван: ставь null. Не добавляй моделей, которых нет в тексте."
)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def cache_key(text: str) -> str:
    return "req:" + hashlib.sha256(normalize_text(text).encode()).hexdigest()


def merge(llm: Requirements, rx: Requirements) -> Requirements:
    """Explicit regex findings win for numbers/models; LLM supplies semantics."""
    out = llm.model_copy(deep=True)
    if rx.budget_rub is not None:
        out.budget_rub = rx.budget_rub
    if not out.use_cases:
        out.use_cases = rx.use_cases
    if out.primary_use_case not in out.use_cases:
        out.primary_use_case = out.use_cases[0]
    rg = rx.gaming.resolution if rx.gaming else None
    if rg:
        if out.gaming is None:
            out.gaming = rx.gaming
        else:
            out.gaming.resolution = rg
    out.must_include = list(dict.fromkeys([*rx.must_include, *out.must_include]))
    p, q = out.preferences, rx.preferences
    p.wifi_required = p.wifi_required or q.wifi_required
    p.no_discrete_gpu = p.no_discrete_gpu or q.no_discrete_gpu
    p.min_ram_gb = q.min_ram_gb or p.min_ram_gb
    p.min_storage_gb = q.min_storage_gb or p.min_storage_gb
    if q.form_factor != "any":
        p.form_factor = q.form_factor
    if p.cpu_brand == "any":
        p.cpu_brand = q.cpu_brand
    if p.gpu_brand == "any":
        p.gpu_brand = q.gpu_brand
    return out


def apply_filters(req: Requirements, filters: dict[str, Any] | None) -> Requirements:
    if not filters:
        return req
    out = req.model_copy(deep=True)
    f = filters
    if f.get("budget_rub"):
        out.budget_rub = int(f["budget_rub"])
    if f.get("wifi"):
        out.preferences.wifi_required = True
    if f.get("compact"):
        out.preferences.form_factor = "compact"
    if f.get("cpu_brand") in ("amd", "intel"):
        out.preferences.cpu_brand = f["cpu_brand"]
    if f.get("no_gpu"):
        out.preferences.no_discrete_gpu = True
    return out


async def _ask_llm(llm: LLMClient, text: str) -> Requirements:
    schema = Requirements.model_json_schema()
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}]
    last_err = ""
    for attempt in range(MAX_RETRIES + 1):
        res = await llm.complete(messages, json_schema=schema, max_tokens=700, temperature=0.0)
        try:
            data = extract_json(res.text)
            return Requirements.model_validate(data)
        except (ValueError, ValidationError) as exc:
            last_err = str(exc)[:600]
            log_event(log, "parser.invalid_llm_json", attempt=attempt)
            messages = messages + [
                {"role": "assistant", "content": res.text[:1500]},
                {
                    "role": "user",
                    "content": "Ответ не прошёл валидацию схемы: "
                    f"{last_err}\nВерни исправленный JSON.",
                },
            ]
    raise ValueError(f"LLM returned invalid JSON after retries: {last_err}")


async def parse_requirements(
    text: str,
    llm: LLMClient | None,
    cache: Cache | None = None,
    filters: dict[str, Any] | None = None,
) -> tuple[Requirements, list[dict[str, str]]]:
    warnings: list[dict[str, str]] = []
    key = cache_key(text)
    req: Requirements | None = None
    if cache is not None:
        hit = await cache.get_json(key)
        if hit:
            req = Requirements.model_validate(hit)
    if req is None:
        rx = parse_requirements_fallback(text)
        if llm is None:
            warnings.append(
                {
                    "code": "llm_unavailable",
                    "message_ru": "ИИ-разбор недоступен, запрос разобран упрощённо.",
                }
            )
            req = rx
        else:
            try:
                req = merge(await _ask_llm(llm, text), rx)
                if cache is not None:
                    await cache.set_json(key, req.model_dump(), CACHE_TTL_S)
            except Exception as exc:
                log_event(log, "parser.llm_failed", error=type(exc).__name__)
                warnings.append(
                    {
                        "code": "llm_unavailable",
                        "message_ru": "ИИ-разбор недоступен, запрос разобран упрощённо.",
                    }
                )
                req = rx
    return apply_filters(req, filters), warnings
