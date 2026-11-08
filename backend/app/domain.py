"""Core domain objects shared by catalog, compat, power and recommender."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any

CATEGORIES = ["cpu", "motherboard", "ram", "gpu", "storage", "cpu_cooler", "psu", "case"]

CATEGORY_RU = {
    "cpu": "Процессор",
    "motherboard": "Материнская плата",
    "ram": "Оперативная память",
    "gpu": "Видеокарта",
    "storage": "Накопитель",
    "cpu_cooler": "Охлаждение CPU",
    "psu": "Блок питания",
    "case": "Корпус",
}

# Fields without which a component is never auto-selected (TZ 6, MISSING_DATA).
CRITICAL_FIELDS: dict[str, list[str]] = {
    "cpu": ["socket", "cores", "threads", "tdp_w", "has_igpu", "memory_types"],
    "motherboard": [
        "socket",
        "form_factor",
        "memory_type",
        "memory_slots",
        "max_memory_gb",
        "m2_slots",
    ],
    "ram": ["type", "capacity_gb_total", "modules"],
    "gpu": ["length_mm", "tdp_w"],
    "storage": ["type", "capacity_gb"],
    "cpu_cooler": ["type", "sockets"],
    "psu": ["wattage_w", "form_factor"],
    "case": [
        "supported_mb_form_factors",
        "max_gpu_length_mm",
        "max_cooler_height_mm",
        "psu_form_factor",
    ],
}


@dataclass(frozen=True, eq=False)
class Component:
    id: int
    category: str
    brand: str
    model: str
    name: str
    specs: dict[str, Any]
    perf_score: float | None = None  # gpu: score; cpu: gaming score
    perf_multicore: float | None = None  # cpu only
    perf_estimated: bool = False
    price_rub: float | None = None
    in_stock: bool = False
    price_source: str | None = None
    price_updated_at: str | None = None
    source: str = "seed"
    source_ref: str | None = None
    embedding: tuple[float, ...] | None = field(default=None, repr=False)

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Component) and other.id == self.id

    def spec(self, key: str) -> Any:
        return self.specs.get(key)

    def missing_critical(self) -> list[str]:
        return [f for f in CRITICAL_FIELDS.get(self.category, []) if self.specs.get(f) is None]

    @property
    def purchasable(self) -> bool:
        return self.price_rub is not None and self.in_stock


@dataclass
class Build:
    cpu: Component | None = None
    motherboard: Component | None = None
    ram: Component | None = None
    gpu: Component | None = None
    cpu_cooler: Component | None = None
    psu: Component | None = None
    case: Component | None = None
    storage: list[Component] = field(default_factory=list)

    def components(self) -> list[Component]:
        singles = [
            self.cpu,
            self.motherboard,
            self.ram,
            self.gpu,
            self.cpu_cooler,
            self.psu,
            self.case,
        ]
        return [c for c in singles if c is not None] + list(self.storage)

    def _copy(self) -> Build:
        return dataclasses.replace(self, storage=list(self.storage))

    def with_component(self, comp: Component) -> Build:
        """Return a copy with `comp` put into its slot (storage is replaced as a single drive)."""
        nb = self._copy()
        if comp.category == "storage":
            nb.storage = [comp]
        else:
            setattr(nb, comp.category, comp)
        return nb

    def without(self, category: str) -> Build:
        nb = self._copy()
        if category == "storage":
            nb.storage = []
        else:
            setattr(nb, category, None)
        return nb

    @property
    def total_price(self) -> float:
        return float(sum(c.price_rub or 0 for c in self.components()))

    @classmethod
    def from_components(cls, comps: list[Component]) -> Build:
        b = cls()
        for c in comps:
            if c.category == "storage":
                b.storage.append(c)
            else:
                setattr(b, c.category, c)
        return b


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str  # "error" | "warning"
    message_ru: str
    components: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message_ru": self.message_ru,
            "components": list(self.components),
        }
