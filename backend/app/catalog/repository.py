"""In-memory catalog. The catalog is small (hundreds..thousands of rows), so the
recommender works on an immutable snapshot loaded from the DB (or from seed files)."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from rapidfuzz import fuzz

from app.catalog.perf import PerfTable, resolve_perf
from app.config import get_settings
from app.domain import CATEGORIES, Component
from app.pricing.providers import CsvPriceProvider, MockPriceProvider, PriceProvider

log = logging.getLogger("catalog")


class Catalog:
    def __init__(self, components: list[Component], mode: str = "seed") -> None:
        self.components = sorted(components, key=lambda c: c.id)
        self.by_id = {c.id: c for c in self.components}
        self.mode = mode
        self.by_category: dict[str, list[Component]] = {c: [] for c in CATEGORIES}
        for c in self.components:
            self.by_category.setdefault(c.category, []).append(c)

    def __len__(self) -> int:
        return len(self.components)

    def get(self, cid: int) -> Component | None:
        return self.by_id.get(cid)

    def search(
        self, q: str | None = None, category: str | None = None, limit: int = 20
    ) -> list[Component]:
        pool = self.by_category.get(category, []) if category else self.components
        if not q:
            return pool[:limit]
        ql = q.lower().strip()
        scored = []
        for c in pool:
            name = c.name.lower()
            score = 100.0 if ql in name else fuzz.partial_ratio(ql, name) * 0.9
            if score >= 60:
                scored.append((-score, c.id, c))
        scored.sort(key=lambda t: (t[0], t[1]))
        return [c for _, _, c in scored[:limit]]


def build_seed_components(
    seed_dir: str | Path, perf_path: str | Path | None, price_provider: str | None = None
) -> list[Component]:
    """Load seed JSON, attach perf scores and prices. Ids are stable (sorted insertion)."""
    seed_dir = Path(seed_dir)
    perf = PerfTable(perf_path)
    raw: list[dict] = []
    for cat in CATEGORIES:
        p = seed_dir / f"{cat}.json"
        if p.exists():
            raw.extend(json.loads(p.read_text(encoding="utf-8")))
    base: list[Component] = []
    for i, r in enumerate(raw, start=1):
        pf = resolve_perf(perf, r["category"], r["model"], r["specs"].get("chipset"), r["specs"])
        base.append(
            Component(
                id=i,
                category=r["category"],
                brand=r["brand"],
                model=r["model"],
                name=r["name"],
                specs=r["specs"],
                perf_score=pf.score if pf else None,
                perf_multicore=pf.multicore if pf else None,
                perf_estimated=pf.estimated if pf else False,
                source="seed",
                source_ref=f"{r['category']}/{r['name']}",
            )
        )
    kind = price_provider or get_settings().price_provider
    csv_path = seed_dir / "prices.csv"
    if kind == "mock" or not csv_path.exists():
        provider: PriceProvider = MockPriceProvider(base)
    else:
        csv_provider = CsvPriceProvider(csv_path, base)
        if csv_provider.unmatched:
            log.warning("unmatched price rows: %s", csv_provider.unmatched)
        provider = csv_provider
    ids = [c.id for c in base]
    if _in_loop():  # called from async code: run the provider on its own loop in a thread
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(1) as ex:
            prices = ex.submit(lambda: asyncio.run(provider.get_prices(ids))).result()
    else:
        prices = asyncio.run(provider.get_prices(ids))
    return _apply_prices(base, prices)


def _in_loop() -> bool:
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


def _apply_prices(base: list[Component], prices: dict) -> list[Component]:
    out = []
    for c in base:
        p = prices.get(c.id)
        out.append(
            Component(
                **{
                    **c.__dict__,
                    "price_rub": p.price_rub if p else None,
                    "in_stock": bool(p and p.in_stock),
                    "price_source": p.source if p else None,
                    "price_updated_at": p.updated_at if p else None,
                }
            )
        )
    return out


async def build_seed_components_async(seed_dir, perf_path, price_provider=None) -> list[Component]:
    return await asyncio.to_thread(build_seed_components, seed_dir, perf_path, price_provider)


_catalog: Catalog | None = None


def set_catalog(catalog: Catalog | None) -> None:
    global _catalog
    _catalog = catalog


async def get_catalog() -> Catalog:
    """DB catalog if it has rows, otherwise the bundled seed (offline fallback)."""
    global _catalog
    if _catalog is not None:
        return _catalog
    s = get_settings()
    comps: list[Component] = []
    mode = "seed"
    try:
        from app.catalog.db_loader import load_db_components

        comps = await load_db_components()
        if comps:
            mode = "db"
    except Exception as exc:  # DB down or not migrated: fall back to seed files
        log.warning("DB catalog unavailable (%s); using seed files", type(exc).__name__)
    if not comps:
        comps = await build_seed_components_async(s.seed_dir, s.perf_scores_path)
    _catalog = Catalog(comps, mode)
    return _catalog
