"""Recommendation pipeline steps 2-6 (TZ 8): budget -> candidates -> beam -> scoring -> variants."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from app.catalog.repository import Catalog
from app.compat import check_build, rule_report
from app.config import get_settings
from app.domain import Build, Component, Issue
from app.llm.schemas import Requirements
from app.power.calc import PowerBreakdown, calculate_power
from app.recommender import scoring
from app.recommender.budget import Profile, build_profile
from app.recommender.engine import Constraints, Searcher, default_config

LABELS = ["Оптимальная", "Экономичная", "Максимум за бюджет"]
KEY_CATS = ["cpu", "gpu", "ram", "storage", "motherboard"]


@dataclass
class Rec:
    label: str
    build: Build
    score: float
    power: PowerBreakdown
    issues: list[Issue]
    warnings: list[dict[str, str]] = field(default_factory=list)
    over_budget: bool = False

    @property
    def total(self) -> float:
        return self.build.total_price

    def compat_report(self) -> list[dict[str, Any]]:
        return rule_report(self.build, self.issues)


@dataclass
class RecommendResult:
    requirements: Requirements
    budget: int
    recs: list[Rec]
    warnings: list[dict[str, str]]
    profile: Profile | None = None
    min_feasible_price: float | None = None


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def resolve_must_include(
    catalog: Catalog, names: list[str]
) -> tuple[dict[str, Component], list[str]]:
    forced: dict[str, Component] = {}
    missing: list[str] = []
    for q in names:
        nq = _norm(q)
        hits = [c for c in catalog.components if c.purchasable and nq and nq in _norm(c.name)]
        if not hits:
            missing.append(q)
            continue
        hits.sort(key=lambda c: (len(c.name), c.id))
        forced.setdefault(hits[0].category, hits[0])
    return forced, missing


def _n_diff(a: Build, b: Build) -> int:
    n = 0
    for cat in KEY_CATS:
        ca = a.storage[0] if cat == "storage" and a.storage else getattr(a, cat, None)
        cb = b.storage[0] if cat == "storage" and b.storage else getattr(b, cat, None)
        if (ca.id if ca else None) != (cb.id if cb else None):
            n += 1
    return n


def _finish(
    label: str,
    b: Build,
    req: Requirements,
    prof: Profile,
    budget: int,
    w_value: float,
    over_budget: bool = False,
) -> Rec:
    issues = check_build(b)
    power = calculate_power(b)
    warns: list[dict[str, str]] = []
    for i in issues:
        if i.severity == "warning":
            warns.append({"code": i.code, "message_ru": i.message_ru})
    res = req.gaming.resolution if req.gaming else None
    if res == "4k" and b.gpu is not None and (b.gpu.perf_score or 0) < 35:
        warns.append(
            {
                "code": "weak_for_4k",
                "message_ru": "Для игр в 4K эта видеокарта слабовата: ожидайте низкий FPS "
                "или сниженные настройки.",
            }
        )
    if "gaming" in req.use_cases and b.gpu is None:
        warns.append(
            {
                "code": "igpu_only",
                "message_ru": "Сборка без дискретной видеокарты: для игр подойдёт слабо.",
            }
        )
    if budget and b.total_price < 0.6 * budget and not over_budget:
        warns.append(
            {
                "code": "well_under_budget",
                "message_ru": "Сборка заметно дешевле бюджета: можно взять более мощную.",
            }
        )
    score = scoring.score_build(b, req, prof, budget, w_value, len(warns))
    return Rec(label, b, round(score, 4), power, issues, warns, over_budget)


def _pick(builds: list[Build], chosen: list[Build], min_diff: int = 2) -> Build | None:
    for b in builds:
        if all(_n_diff(b, c) >= min_diff for c in chosen):
            return b
    return None


def recommend(catalog: Catalog, req: Requirements) -> RecommendResult:
    s = get_settings()
    warnings: list[dict[str, str]] = []
    budget = req.budget_rub
    if budget is None:
        budget = s.default_budget_rub
        req = req.model_copy(update={"budget_assumed": True})
        warnings.append(
            {
                "code": "budget_assumed",
                "message_ru": f"Бюджет не указан, подбираю в пределах "
                f"{budget:,} ₽ по умолчанию.".replace(",", " "),
            }
        )
    prof = build_profile(req, budget)
    forced, missing = resolve_must_include(catalog, req.must_include)
    for q in missing:
        warnings.append(
            {
                "code": "must_include_not_found",
                "message_ru": f"Модель «{q}» не найдена в каталоге (или нет в наличии).",
            }
        )
    light_only = set(req.use_cases) <= {"office", "study", "programming"}
    if req.preferences.no_discrete_gpu or (light_only and req.preferences.gpu_brand == "any"):
        gpu_mode = "none"
    elif prof.gpu_required:
        gpu_mode = "required"
    else:
        gpu_mode = "optional"

    levels: list[tuple[str, Constraints]] = [
        ("full", Constraints(req, prof, forced, True, gpu_mode)),
    ]
    if forced:
        levels.append(("no_forced", Constraints(req, prof, {}, True, gpu_mode)))
    levels.append(("soft_relaxed", Constraints(req, prof, {}, False, gpu_mode)))

    for name, cons in levels:
        searcher = Searcher(catalog, cons)
        a = searcher.run(default_config(budget, budget, w_value=0.15))
        if not a:
            continue
        if name == "no_forced":
            warnings.append(
                {
                    "code": "must_include_dropped",
                    "message_ru": "Указанные модели несовместимы с бюджетом или между "
                    "собой, подобрал без них.",
                }
            )
        if name == "soft_relaxed":
            warnings.append(
                {
                    "code": "preferences_relaxed",
                    "message_ru": "Пожелания (бренд, Wi-Fi, форм-фактор, объём) пришлось "
                    "ослабить, чтобы уложиться в бюджет.",
                }
            )
        eco = searcher.run(default_config(budget, budget * 0.8, w_value=0.6))
        mx = searcher.run(default_config(budget, budget, mode="perf"))
        chosen: list[Build] = []
        recs: list[Rec] = []
        first = a[0]
        chosen.append(first)
        recs.append(_finish(LABELS[0], first, req, prof, budget, 0.15))
        for label, pool, wv in ((LABELS[1], eco, 0.6), (LABELS[2], mx, 0.0)):
            pool_sorted = (
                pool
                if label == LABELS[1]
                else sorted(
                    pool,
                    key=lambda b: (
                        -scoring.score_build(b, req, prof, budget, 0.0),
                        b.total_price,
                        tuple(c.id for c in b.components()),
                    ),
                )
            )
            if label == LABELS[1]:
                band = [b for b in pool_sorted if 0.65 * budget <= b.total_price <= 0.85 * budget]
                pool_sorted = (
                    band or [b for b in pool_sorted if b.total_price <= 0.9 * budget] or pool_sorted
                )
            pick = _pick(pool_sorted, chosen) or _pick(a, chosen)
            if pick is not None:
                chosen.append(pick)
                recs.append(_finish(label, pick, req, prof, budget, wv))
        return RecommendResult(req, budget, recs, warnings, prof)

    # Nothing fits: return the closest valid (cheapest) build and say so.
    cons = Constraints(req, prof, {}, False, gpu_mode)
    searcher = Searcher(catalog, cons)
    cheapest = searcher.run(default_config(budget, math.inf, mode="min_cost"))
    if not cheapest and gpu_mode == "required":  # last resort: allow iGPU-only
        cons = Constraints(req, prof, {}, False, "optional")
        searcher = Searcher(catalog, cons)
        cheapest = searcher.run(default_config(budget, math.inf, mode="min_cost"))
    if not cheapest:
        warnings.append(
            {
                "code": "no_build",
                "message_ru": "Не удалось собрать совместимую конфигурацию из каталога.",
            }
        )
        return RecommendResult(req, budget, [], warnings, prof)
    b = cheapest[0]
    price = round(b.total_price)
    warnings.append(
        {
            "code": "over_budget",
            "message_ru": f"Бюджет недостаточен: ближайшая возможная сборка стоит "
            f"{price:,} ₽.".replace(",", " "),
        }
    )
    rec = _finish("Ближайшая возможная", b, req, prof, budget, 0.0, over_budget=True)
    return RecommendResult(req, budget, [rec], warnings, prof, min_feasible_price=price)
