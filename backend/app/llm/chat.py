"""Build chat (TZ 9.3): intent classification -> backend tools -> streamed, validated answer.

Tool calling is not assumed: we use the 'classify first, call backend functions ourselves'
path from the TZ, which works with any OpenRouter model."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.catalog.repository import Catalog
from app.core.builds import BuildView, llm_context
from app.core.logging import log_event
from app.core.store import Store
from app.domain import CATEGORY_RU
from app.llm.client import LLMClient, extract_json
from app.llm.explain import template_explanation
from app.llm.validator import Vocabulary, validate_and_fix
from app.rag.alternatives import Alternative, find_alternatives

log = logging.getLogger("chat")

CAT_WORDS = {
    "gpu": r"видеокарт|\bgpu\b|видюх|графическ",
    "cpu": r"процессор|\bcpu\b|камен",
    "ram": r"оператив|\bозу\b|\bram\b|памят",
    "motherboard": r"материнск|\bплат",
    "storage": r"накопител|\bssd\b|\bhdd\b|диск",
    "psu": r"блок питани|\bбп\b|питани",
    "case": r"корпус",
    "cpu_cooler": r"кулер|охлажден|сжо",
}
CHEAPER = r"дешевл|подешевле|бюджетн|сэконом|экономи|дешёв|дешев|снизить цен|меньше денег"
BETTER = r"мощнее|лучше|быстрее|производительн|апгрейд|усилить|помощнее"
SIMILAR = r"замен|аналог|вместо|альтернатив|чем заменить|другой|другую"
EXPLAIN = r"почему|зачем|объясни|расскажи|обоснуй|чем хорош|для чего"

SYSTEM = (
    "Ты — консультант по сборке ПК в чате. Отвечай по-русски, дружелюбно и кратко, в Markdown. "
    "Опирайся ТОЛЬКО на JSON со сборкой и (если есть) списком аналогов. Не называй "
    "комплектующие, которых нет в этих данных. Если данных не хватает, так и скажи: «нет "
    "данных». Не обещай FPS и цифры, которых нет в данных. Если переданы аналоги — кратко "
    "сравни их по цене и производительности и порекомендуй один."
)


@dataclass
class Intent:
    kind: str  # explain | alternatives | other
    category: str | None = None
    direction: str = "similar"


def keyword_intent(msg: str, default_cat: str | None = None) -> Intent:
    t = msg.lower()
    cat = next((c for c, p in CAT_WORDS.items() if re.search(p, t)), None)
    direction = (
        "cheaper" if re.search(CHEAPER, t) else "better" if re.search(BETTER, t) else "similar"
    )
    wants_alt = bool(re.search(CHEAPER, t) or re.search(BETTER, t) or re.search(SIMILAR, t))
    if wants_alt:
        return Intent("alternatives", cat or default_cat or "gpu", direction)
    if re.search(EXPLAIN, t):
        return Intent("explain", cat)
    return Intent("other", cat)


async def classify(llm: LLMClient | None, msg: str) -> Intent:
    kw = keyword_intent(msg)
    if llm is None or kw.kind != "other":
        return kw
    prompt = (
        'Определи намерение сообщения о сборке ПК. Верни JSON: {"intent": '
        '"explain|alternatives|other", "category": "cpu|motherboard|ram|gpu|storage|'
        'cpu_cooler|psu|case|null", "direction": "cheaper|better|similar"}.'
    )
    try:
        res = await llm.complete(
            [{"role": "system", "content": prompt}, {"role": "user", "content": msg}],
            max_tokens=80,
            temperature=0.0,
        )
        d = extract_json(res.text)
        kind = d.get("intent", "other")
        if kind in ("explain", "alternatives", "other"):
            cat = d.get("category") if d.get("category") in CATEGORY_RU else None
            return Intent(
                kind,
                cat or ("gpu" if kind == "alternatives" else None),
                d.get("direction")
                if d.get("direction") in ("cheaper", "better", "similar")
                else "similar",
            )
    except Exception as exc:
        log_event(log, "chat.classify_failed", error=type(exc).__name__)
    return kw


def alt_to_dict(a: Alternative) -> dict:
    c = a.component
    return {
        "component_id": c.id,
        "name": c.name,
        "category": c.category,
        "price_rub": c.price_rub,
        "price_delta_rub": a.price_delta_rub,
        "total_delta_rub": a.total_delta_rub,
        "perf_delta_pct": a.perf_delta_pct,
        "compat_ok": a.compat_ok,
        "notes": a.notes,
        "extra_component_id": a.extra_component.id if a.extra_component else None,
        "extra_component_name": a.extra_component.name if a.extra_component else None,
    }


def template_answer(
    intent: Intent, view: BuildView, alts: list[Alternative], requirements: dict | None
) -> str:
    if intent.kind == "alternatives":
        cat_ru = CATEGORY_RU.get(intent.category or "", "компонент").lower()
        if not alts:
            return (
                f"Не нашёл подходящих вариантов замены для категории «{cat_ru}», которые "
                "были бы совместимы с остальной сборкой."
            )
        lines = [f"Варианты замены ({cat_ru}), совместимые с остальной сборкой:"]
        for a in alts:
            perf = (
                f", производительность {a.perf_delta_pct:+.0f}%"
                if a.perf_delta_pct is not None
                else ""
            )
            lines.append(
                f"- **{a.component.name}** — {a.total_delta_rub:+,.0f} ₽{perf}".replace(",", " ")
            )
        lines.append("\nНажмите «Применить» на карточке, чтобы пересобрать сборку.")
        return "\n".join(lines)
    if intent.kind == "explain":
        return template_explanation(view, requirements)
    return (
        "Я могу объяснить выбор комплектующих или предложить замену: например, "
        "«почему эта видеокарта?», «можно дешевле?», «чем заменить процессор?»."
    )


def _history_messages(history: list[dict]) -> list[dict[str, str]]:
    return [{"role": m["role"], "content": m["content"]} for m in history[-10:]]


async def chat_events(
    view: BuildView,
    requirements: dict | None,
    message: str,
    catalog: Catalog,
    llm: LLMClient | None,
    store: Store,
) -> AsyncIterator[dict]:
    history = await store.get_chat(view.id, limit=10)
    await store.add_chat(view.id, "user", message)
    intent = await classify(llm, message)
    alts: list[Alternative] = []
    if intent.kind == "alternatives" and intent.category:
        alts = find_alternatives(catalog, view.build, intent.category, intent.direction, k=3)
        yield {
            "event": "alternatives",
            "data": {
                "category": intent.category,
                "intent": intent.direction,
                "items": [alt_to_dict(a) for a in alts],
            },
        }
    allowed = (
        list(view.build.components())
        + [a.component for a in alts]
        + [a.extra_component for a in alts if a.extra_component is not None]
    )
    vocab = Vocabulary(allowed, catalog.components)

    if llm is None:
        text = template_answer(intent, view, alts, requirements)
        for i in range(0, len(text), 50):
            yield {"event": "token", "data": {"text": text[i : i + 50]}}
        await store.add_chat(view.id, "assistant", text)
        yield {"event": "done", "data": {"text": text, "source": "template"}}
        return

    ctx = llm_context(view, requirements)
    payload = {
        "build": ctx,
        "alternatives": [alt_to_dict(a) for a in alts],
        "intent": {"kind": intent.kind, "category": intent.category, "direction": intent.direction},
    }

    def msgs(banned: list[str] | None = None) -> list[dict[str, str]]:
        sys = SYSTEM + ("\nНЕ упоминай: " + ", ".join(banned) if banned else "")
        return (
            [
                {"role": "system", "content": sys},
                {
                    "role": "system",
                    "content": "Данные (JSON): " + json.dumps(payload, ensure_ascii=False),
                },
            ]
            + _history_messages(history)
            + [{"role": "user", "content": message}]
        )

    buf: list[str] = []
    try:
        async for tok in llm.stream(msgs(), max_tokens=700):
            buf.append(tok)
            yield {"event": "token", "data": {"text": tok}}
    except Exception as exc:
        log_event(log, "chat.llm_failed", error=type(exc).__name__)
        if not buf:
            text = template_answer(intent, view, alts, requirements)
            yield {"event": "replace", "data": {"text": text}}
            await store.add_chat(view.id, "assistant", text)
            yield {"event": "done", "data": {"text": text, "source": "template"}}
            return
    raw = "".join(buf)

    async def regen(banned: list[str]) -> str:
        return (await llm.complete(msgs(banned), max_tokens=700)).text

    text, bad = await validate_and_fix(raw, vocab, regen)
    if text != raw:
        yield {"event": "replace", "data": {"text": text}}
    await store.add_chat(view.id, "assistant", text)
    yield {"event": "done", "data": {"text": text, "source": "llm", "violations": len(bad)}}
