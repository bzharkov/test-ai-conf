from __future__ import annotations

from typing import Any

from app.catalog.repository import Catalog
from app.core.builds import BuildView
from app.domain import CATEGORIES, CATEGORY_RU, Component
from app.schemas.api import (
    BuildOut,
    BuildSummary,
    Compatibility,
    ComponentOut,
    IssueOut,
    KeyComponents,
    PowerOut,
    Warn,
)


def is_demo(c: Component) -> bool:
    src = (c.price_source or "").lower()
    return "демо" in src or "demo" in src or "ориентиров" in src


def component_out(c: Component) -> ComponentOut:
    return ComponentOut(
        id=c.id,
        category=c.category,
        category_ru=CATEGORY_RU[c.category],
        brand=c.brand,
        model=c.model,
        name=c.name,
        specs=c.specs,
        perf_score=c.perf_score,
        perf_multicore=c.perf_multicore,
        perf_estimated=c.perf_estimated,
        price_rub=c.price_rub,
        in_stock=c.in_stock,
        price_source=c.price_source,
        price_updated_at=c.price_updated_at,
        price_is_demo=is_demo(c),
        source=c.source,
    )


def summary(view: BuildView) -> BuildSummary:
    b = view.build
    return BuildSummary(
        id=view.id,
        label=view.label,
        total_price=round(view.total),
        budget_rub=view.budget,
        budget_share=round(view.total / view.budget, 3) if view.budget else None,
        over_budget=view.over_budget,
        compat_ok=view.compat_ok,
        prices_are_demo=any(is_demo(c) for c in b.components()),
        key_components=KeyComponents(
            cpu=b.cpu.name if b.cpu else None,
            gpu=b.gpu.name if b.gpu else None,
            ram=b.ram.name if b.ram else None,
            storage=b.storage[0].name if b.storage else None,
        ),
        warnings=[Warn(**w) for w in view.warnings],
    )


def build_out(view: BuildView, requirements: Any = None) -> BuildOut:
    b = view.build
    ordered = sorted(b.components(), key=lambda c: CATEGORIES.index(c.category))
    p = view.power.as_dict()
    return BuildOut(
        **summary(view).model_dump(),
        request_id=view.request_id,
        created_at=view.created_at,
        items=[component_out(c) for c in ordered],
        power=PowerOut(**p, installed_psu_w=b.psu.spec("wattage_w") if b.psu else None),
        compatibility=Compatibility(
            ok=view.compat_ok,
            rules=view.rules(),  # type: ignore[arg-type]
            issues=[IssueOut(**i.as_dict()) for i in view.issues],
        ),
        explanation=view.explanation,
        requirements=requirements,
    )


def catalog_size(catalog: Catalog) -> int:
    return len(catalog)
