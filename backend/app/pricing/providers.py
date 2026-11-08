"""Price providers (TZ 5.3). Real shop scraping is intentionally NOT implemented."""

from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from rapidfuzz import fuzz, process

from app.domain import Component


@dataclass(frozen=True)
class PriceInfo:
    price_rub: float
    in_stock: bool
    source: str
    updated_at: str


class PriceProvider(Protocol):
    async def get_prices(self, component_ids: list[int]) -> dict[int, PriceInfo]: ...


def normalize_name(s: str) -> str:
    return re.sub(r"[^a-z0-9а-я]+", " ", s.lower()).strip()


class CsvPriceProvider:
    """Reads `sku_or_name, price_rub, in_stock, source, updated_at`; matches by name."""

    def __init__(
        self, csv_path: str | Path, components: list[Component], fuzzy_threshold: float = 92.0
    ) -> None:
        self.unmatched: list[str] = []
        self._prices: dict[int, PriceInfo] = {}
        by_exact = {c.name: c.id for c in components}
        by_norm = {normalize_name(c.name): c.id for c in components}
        norm_keys = list(by_norm)
        with open(csv_path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                key = row["sku_or_name"].strip()
                cid = by_exact.get(key) or by_norm.get(normalize_name(key))
                if cid is None and norm_keys:
                    hit = process.extractOne(normalize_name(key), norm_keys, scorer=fuzz.ratio)
                    if hit and hit[1] >= fuzzy_threshold:
                        cid = by_norm[hit[0]]
                if cid is None:
                    self.unmatched.append(key)
                    continue
                self._prices[cid] = PriceInfo(
                    price_rub=float(row["price_rub"]),
                    in_stock=row["in_stock"].strip().lower() in ("1", "true", "yes", "да"),
                    source=row.get("source") or "csv",
                    updated_at=row.get("updated_at") or "",
                )

    async def get_prices(self, component_ids: list[int]) -> dict[int, PriceInfo]:
        return {i: self._prices[i] for i in component_ids if i in self._prices}


class MockPriceProvider:
    """Deterministic heuristic price: category base + perf, jittered by a stable hash."""

    BASE = {
        "cpu": 5000,
        "motherboard": 6000,
        "ram": 3000,
        "gpu": 10000,
        "storage": 3000,
        "cpu_cooler": 1500,
        "psu": 4000,
        "case": 4000,
    }
    PERF_K = {"cpu": 600, "gpu": 2800}

    def __init__(self, components: list[Component], seed: str = "pcconf") -> None:
        self._by_id = {c.id: c for c in components}
        self._seed = seed

    async def get_prices(self, component_ids: list[int]) -> dict[int, PriceInfo]:
        out: dict[int, PriceInfo] = {}
        for i in component_ids:
            c = self._by_id.get(i)
            if c is None:
                continue
            price = self.BASE.get(c.category, 3000) + (c.perf_score or 0) * self.PERF_K.get(
                c.category, 0
            )
            if c.category == "ram":
                price += 220 * float(c.spec("capacity_gb_total") or 8)
            if c.category == "storage":
                price += 4 * float(c.spec("capacity_gb") or 0)
            if c.category == "psu":
                price += 7 * float(c.spec("wattage_w") or 0)
            h = int(hashlib.sha256(f"{self._seed}:{c.name}".encode()).hexdigest()[:6], 16)
            price *= 0.9 + (h % 2000) / 10000.0
            out[i] = PriceInfo(
                round(price / 100) * 100, True, "ориентировочная цена (демо)", "2026-11-01"
            )
        return out
