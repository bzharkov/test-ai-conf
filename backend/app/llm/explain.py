"""Build explanation: LLM (data-only prompt) + validation, with a deterministic template."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from app.catalog.repository import Catalog
from app.core.builds import BuildView, llm_context
from app.core.logging import log_event
from app.llm.client import LLMClient
from app.llm.validator import Vocabulary, validate_and_fix

log = logging.getLogger("explain")

SYSTEM = (
    "Ты — консультант по сборке ПК. Отвечай по-русски, коротко и по делу, в Markdown. "
    "Опирайся ТОЛЬКО на переданные данные о сборке. Не называй комплектующие, которых нет в "
    "данных (никаких других моделей процессоров, видеокарт и т.д.). Если ответа нет в данных, "
    "так и скажи: «нет данных». Структура ответа: «Под какую задачу», «Почему этот CPU/GPU», "
    "«Баланс и запас», «Что можно улучшить»."
)


def template_explanation(view: BuildView, requirements: dict | None) -> str:
    b = view.build
    uc = ", ".join((requirements or {}).get("use_cases", [])) or "общие задачи"
    lines = [
        f"### Под какую задачу\nСборка «{view.label}» подобрана под: {uc}. "
        f"Итоговая стоимость — {round(view.total):,} ₽".replace(",", " ")
        + (f" при бюджете {view.budget:,} ₽." if view.budget else ".").replace(",", " ")
    ]
    why = []
    if b.cpu:
        why.append(
            f"процессор {b.cpu.name} ({b.cpu.spec('cores')} ядер / "
            f"{b.cpu.spec('threads')} потоков, до {b.cpu.spec('boost_clock_ghz')} ГГц)"
        )
    if b.gpu:
        why.append(f"видеокарта {b.gpu.name} ({b.gpu.spec('vram_gb')} ГБ видеопамяти)")
    else:
        why.append("дискретной видеокарты нет — используется встроенная графика процессора")
    lines.append("### Почему этот CPU/GPU\n" + "; ".join(why) + ".")
    ram = b.ram.spec("capacity_gb_total") if b.ram else None
    lines.append(
        f"### Баланс и запас\nОЗУ: {ram} ГБ. Оценочное потребление — "
        f"{round(view.power.estimated_power_w)} Вт, рекомендуемый БП — от "
        f"{view.power.psu_recommended_w} Вт, установлен {b.psu.spec('wattage_w')} Вт "
        f"({b.psu.name}). Все проверки совместимости пройдены."
        if b.psu and view.compat_ok
        else "### Баланс и запас\nЕсть замечания по совместимости, см. блок проверок."
    )
    tips = [w["message_ru"] for w in view.warnings] or [
        "Для апгрейда можно спросить в чате про замену видеокарты или процессора."
    ]
    lines.append("### Что можно улучшить\n" + "\n".join(f"- {t}" for t in tips))
    return "\n\n".join(lines)


def _messages(view: BuildView, requirements: dict | None, banned: list[str] | None = None):
    user = "Данные сборки (JSON):\n" + json.dumps(
        llm_context(view, requirements), ensure_ascii=False
    )
    if banned:
        user += (
            "\n\nВ прошлом ответе были упомянуты модели вне сборки: "
            f"{', '.join(banned)}. Не упоминай их."
        )
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


async def explanation_events(
    view: BuildView, requirements: dict | None, catalog: Catalog, llm: LLMClient | None
) -> AsyncIterator[dict]:
    """Yields {'event': 'token'|'replace'|'done'|'error', 'data': {...}}; final text in done."""
    if llm is None:
        text = template_explanation(view, requirements)
        for i in range(0, len(text), 60):
            yield {"event": "token", "data": {"text": text[i : i + 60]}}
        yield {"event": "done", "data": {"text": text, "source": "template"}}
        return
    vocab = Vocabulary(view.build.components(), catalog.components)
    buf: list[str] = []
    try:
        async for tok in llm.stream(_messages(view, requirements), max_tokens=900):
            buf.append(tok)
            yield {"event": "token", "data": {"text": tok}}
    except Exception as exc:
        log_event(log, "explain.llm_failed", error=type(exc).__name__)
        if not buf:
            text = template_explanation(view, requirements)
            yield {"event": "replace", "data": {"text": text}}
            yield {"event": "done", "data": {"text": text, "source": "template"}}
            return
    raw = "".join(buf)

    async def regen(banned: list[str]) -> str:
        res = await llm.complete(_messages(view, requirements, banned), max_tokens=900)
        return res.text

    text, bad = await validate_and_fix(raw, vocab, regen)
    if text != raw:
        yield {"event": "replace", "data": {"text": text}}
    yield {"event": "done", "data": {"text": text, "source": "llm", "violations": len(bad)}}
