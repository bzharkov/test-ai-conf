"""Stored build <-> domain objects, plus the JSON the LLM is allowed to see."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.catalog.repository import Catalog
from app.compat import check_build, rule_report
from app.domain import CATEGORIES, CATEGORY_RU, Build, Issue
from app.power.calc import PowerBreakdown, calculate_power
from app.recommender.service import Rec


@dataclass
class BuildView:
    id: int
    request_id: int | None
    label: str
    build: Build
    total: float
    power: PowerBreakdown
    issues: list[Issue]
    warnings: list[dict[str, str]]
    score: float
    explanation: str | None
    over_budget: bool
    budget: int | None
    created_at: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def compat_ok(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    def rules(self) -> list[dict[str, Any]]:
        return rule_report(self.build, self.issues)


def _items(build: Build) -> list[dict[str, Any]]:
    return [
        {"category": c.category, "component_id": c.id, "name": c.name, "price_rub": c.price_rub}
        for c in build.components()
    ]


def to_stored(rec: Rec, request_id: int | None, budget: int | None) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "label": rec.label,
        "items": _items(rec.build),
        "total_price": rec.total,
        "estimated_power_w": rec.power.estimated_power_w,
        "psu_recommended_w": rec.power.psu_recommended_w,
        "score": rec.score,
        "explanation": None,
        "warnings": rec.warnings,
        "extra": {"over_budget": rec.over_budget, "budget": budget},
    }


def stored_from_build(
    build: Build,
    label: str,
    request_id: int | None,
    budget: int | None,
    score: float,
    warnings: list[dict[str, str]],
) -> dict[str, Any]:
    p = calculate_power(build)
    return {
        "request_id": request_id,
        "label": label,
        "items": _items(build),
        "total_price": build.total_price,
        "estimated_power_w": p.estimated_power_w,
        "psu_recommended_w": p.psu_recommended_w,
        "score": score,
        "explanation": None,
        "warnings": warnings,
        "extra": {"over_budget": bool(budget and build.total_price > budget), "budget": budget},
    }


def hydrate(stored: dict[str, Any], catalog: Catalog) -> BuildView:
    comps = [catalog.get(i["component_id"]) for i in stored["items"]]
    build = Build.from_components([c for c in comps if c is not None])
    extra = stored.get("extra") or {}
    return BuildView(
        id=stored["id"],
        request_id=stored.get("request_id"),
        label=stored["label"],
        build=build,
        total=build.total_price,
        power=calculate_power(build),
        issues=check_build(build),
        warnings=stored.get("warnings") or [],
        score=stored["score"],
        explanation=stored.get("explanation"),
        over_budget=bool(extra.get("over_budget")),
        budget=extra.get("budget"),
        created_at=stored.get("created_at", ""),
        extra=extra,
    )


def key_specs(c) -> dict[str, Any]:
    s = c.specs
    pick = {
        "cpu": ["socket", "cores", "threads", "boost_clock_ghz", "tdp_w", "has_igpu"],
        "motherboard": ["socket", "chipset", "form_factor", "memory_type", "m2_slots", "wifi"],
        "ram": ["type", "capacity_gb_total", "modules", "speed_mhz"],
        "gpu": ["chipset", "vram_gb", "length_mm", "tdp_w"],
        "storage": ["type", "interface", "capacity_gb"],
        "cpu_cooler": ["type", "height_mm", "radiator_mm", "tdp_rating_w"],
        "psu": ["wattage_w", "efficiency", "modular", "form_factor"],
        "case": ["supported_mb_form_factors", "max_gpu_length_mm", "max_cooler_height_mm"],
    }[c.category]
    return {k: s.get(k) for k in pick}


def llm_context(view: BuildView, requirements: dict[str, Any] | None) -> dict[str, Any]:
    """The ONLY data about hardware the model is given (TZ 8.6)."""
    items = []
    for cat in CATEGORIES:
        for c in (
            [view.build.storage[0]]
            if cat == "storage" and view.build.storage
            else [getattr(view.build, cat, None)]
            if cat != "storage"
            else []
        ):
            if c is None:
                continue
            items.append(
                {
                    "category": CATEGORY_RU[cat],
                    "name": c.name,
                    "price_rub": c.price_rub,
                    "perf_score": c.perf_score,
                    "specs": key_specs(c),
                }
            )
    return {
        "requirements": requirements,
        "build_label": view.label,
        "components": items,
        "total_price_rub": round(view.total),
        "budget_rub": view.budget,
        "power": view.power.as_dict(),
        "warnings": [w["message_ru"] for w in view.warnings],
        "compatibility_ok": view.compat_ok,
    }
