"""PSU power estimation (TZ section 7). Coefficients live in Settings."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from app.config import Settings, get_settings
from app.domain import Build


@dataclass
class PowerBreakdown:
    items: list[tuple[str, float]] = field(default_factory=list)
    estimated_power_w: float = 0.0
    psu_recommended_w: int = 0
    gpu_recommended_psu_w: int = 0
    margin: float = 1.3

    def as_dict(self) -> dict[str, Any]:
        return {
            "items": [{"label": label, "watts": round(w)} for label, w in self.items],
            "estimated_power_w": round(self.estimated_power_w),
            "margin": self.margin,
            "gpu_recommended_psu_w": self.gpu_recommended_psu_w,
            "psu_recommended_w": self.psu_recommended_w,
        }


def ceil_to_50(x: float) -> int:
    return int(math.ceil(x / 50.0) * 50)


def calculate_power(
    build: Build, settings: Settings | None = None, extra_w: float = 0.0
) -> PowerBreakdown:
    s = settings or get_settings()
    out = PowerBreakdown(margin=s.power_margin)
    if build.cpu is not None:
        tdp = float(build.cpu.spec("tdp_w") or 0)
        out.items.append((f"Процессор (TDP {tdp:g} Вт × {s.power_k_cpu})", tdp * s.power_k_cpu))
    if build.gpu is not None:
        out.items.append(("Видеокарта (TDP)", float(build.gpu.spec("tdp_w") or 0)))
    if build.motherboard is not None:
        out.items.append(("Материнская плата", 50.0))
    if build.ram is not None:
        out.items.append(
            (
                f"Память ({build.ram.spec('modules') or 1} мод. × 5 Вт)",
                5.0 * float(build.ram.spec("modules") or 1),
            )
        )
    per_type = {"nvme": 5.0, "sata_ssd": 8.0, "hdd": 10.0}
    for d in build.storage:
        out.items.append((f"Накопитель {d.model}", per_type.get(str(d.spec("type")), 8.0)))
    out.items.append(("Вентиляторы/USB", 15.0))
    if extra_w:
        out.items.append(("Запас под накопители", extra_w))
    out.estimated_power_w = sum(w for _, w in out.items)
    if build.gpu is not None:
        out.gpu_recommended_psu_w = int(build.gpu.spec("recommended_psu_w") or 0)
    out.psu_recommended_w = max(
        ceil_to_50(out.estimated_power_w * s.power_margin), out.gpu_recommended_psu_w
    )
    return out
