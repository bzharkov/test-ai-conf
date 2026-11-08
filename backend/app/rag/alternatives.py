"""find_alternatives (TZ 9.2): vector similarity + price/perf intent + full compat re-check."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.catalog.repository import Catalog
from app.catalog.text import component_search_text
from app.compat import check_build, has_errors
from app.domain import Build, Component
from app.power.calc import calculate_power
from app.rag.embeddings import Embedder, cosine, get_embedder

_emb_cache: dict[tuple[str, int], tuple[float, ...]] = {}


@dataclass
class Alternative:
    component: Component
    price_delta_rub: float
    perf_delta_pct: float | None
    compat_ok: bool
    notes: list[str] = field(default_factory=list)
    extra_component: Component | None = None  # e.g. a PSU upgrade needed for this swap

    @property
    def total_delta_rub(self) -> float:
        extra = 0.0
        if self.extra_component is not None:
            extra = self.extra_component.price_rub or 0.0
        return self.price_delta_rub + extra


def slot_component(build: Build, category: str) -> Component | None:
    if category == "storage":
        return build.storage[0] if build.storage else None
    return getattr(build, category, None)


def perf_value(c: Component) -> float | None:
    s = c.specs
    if c.category == "cpu":
        if c.perf_score is None or c.perf_multicore is None:
            return None
        return 0.6 * c.perf_score + 0.4 * c.perf_multicore
    if c.category == "gpu":
        return c.perf_score
    if c.category == "ram":
        return float(s["capacity_gb_total"]) * (1 + (s.get("speed_mhz") or 3200) / 20000)
    if c.category == "storage":
        return float(s["capacity_gb"]) * (1.2 if s["type"] == "nvme" else 1.0)
    if c.category == "psu":
        return float(s["wattage_w"])
    return None


def embedding_of(c: Component, emb: Embedder) -> tuple[float, ...]:
    if c.embedding is not None:
        return c.embedding
    key = (emb.name, c.id)
    if key not in _emb_cache:
        _emb_cache[key] = tuple(emb.embed_passages([component_search_text(c)])[0])
    return _emb_cache[key]


def _psu_upgrade(catalog: Catalog, build: Build) -> Component | None:
    need = calculate_power(build).psu_recommended_w
    case_ff = build.case.spec("psu_form_factor") if build.case else None
    opts = [
        p
        for p in catalog.by_category["psu"]
        if p.purchasable
        and p.specs["wattage_w"] >= need
        and not p.missing_critical()
        and (
            case_ff is None
            or p.specs["form_factor"] == case_ff
            or (p.specs["form_factor"] == "SFX" and case_ff == "ATX")
        )
    ]
    return min(opts, key=lambda p: (p.price_rub or 0, p.id), default=None)


def find_alternatives(
    catalog: Catalog,
    build: Build,
    category: str,
    intent: str = "similar",
    k: int = 3,
    embedder: Embedder | None = None,
    exclude_ids: set[int] | None = None,
) -> list[Alternative]:
    cur = slot_component(build, category)
    if cur is None:
        return []
    emb = embedder or get_embedder()
    cur_emb = embedding_of(cur, emb)
    cur_price = cur.price_rub or 0.0
    cur_perf = perf_value(cur)
    pool = []
    for c in catalog.by_category.get(category, []):
        if c.id == cur.id or not c.purchasable or c.missing_critical():
            continue
        if exclude_ids and c.id in exclude_ids:
            continue
        p = c.price_rub or 0.0
        pv = perf_value(c)
        if intent == "cheaper" and not p < cur_price * 0.97:
            continue
        if intent == "better":
            if pv is None or cur_perf is None or not pv > cur_perf * 1.03:
                continue
        if intent == "similar" and abs(p - cur_price) > 0.25 * cur_price:
            continue
        pool.append((-cosine(cur_emb, embedding_of(c, emb)), c.id, c))
    pool.sort(key=lambda t: (t[0], t[1]))
    out: list[Alternative] = []
    for _, _, c in pool[:40]:
        nb = build.with_component(c)
        issues = check_build(nb)
        extra = None
        errs = [i for i in issues if i.severity == "error"]
        if errs and all(i.code == "PSU_POWER" for i in errs) and category in ("gpu", "cpu"):
            extra = _psu_upgrade(catalog, nb)
            if extra is not None:
                nb = nb.with_component(extra)
                issues = check_build(nb)
        if has_errors(issues) or any(i.code == "MISSING_DATA" for i in issues):
            continue
        pv = perf_value(c)
        perf_delta = None
        if pv is not None and cur_perf:
            perf_delta = round((pv - cur_perf) / cur_perf * 100, 1)
        notes = [i.message_ru for i in issues if i.severity == "warning"]
        if extra is not None:
            notes.append(
                f"Потребуется заменить БП на {extra.name} ({extra.specs['wattage_w']} Вт)."
            )
        out.append(
            Alternative(c, round((c.price_rub or 0) - cur_price), perf_delta, True, notes, extra)
        )
        if len(out) >= k:
            break
    return out


def apply_replacement(catalog: Catalog, build: Build, alt: Alternative) -> Build:
    nb = build.with_component(alt.component)
    if alt.extra_component is not None:
        nb = nb.with_component(alt.extra_component)
    return nb
