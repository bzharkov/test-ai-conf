"""Budget allocation by profile (TZ 8.2). Shares are config-driven (profiles.yaml)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.llm.schemas import Requirements

_PATH = Path(__file__).with_name("profiles.yaml")
PRIMARY_WEIGHT = 0.6


@lru_cache
def load_profiles() -> dict[str, Any]:
    return yaml.safe_load(_PATH.read_text(encoding="utf-8"))


@dataclass
class Profile:
    shares: dict[str, tuple[float, float]]  # category -> (share, tolerance)
    weights: dict[str, float]  # gpu, cpu_g, cpu_m, ram, storage
    gpu_required: bool
    min_ram_gb: int
    min_storage_gb: int
    ram_ref_gb: int


def use_case_mix(req: Requirements) -> dict[str, float]:
    ucs = [u for u in dict.fromkeys(req.use_cases)] or ["office"]
    primary = req.primary_use_case if req.primary_use_case in ucs else ucs[0]
    if len(ucs) == 1:
        return {str(ucs[0]): 1.0}
    rest = [u for u in ucs if u != primary]
    mix: dict[str, float] = {str(primary): PRIMARY_WEIGHT}
    for u in rest:
        mix[u] = (1 - PRIMARY_WEIGHT) / len(rest)
    return mix


def build_profile(req: Requirements, budget: int) -> Profile:
    cfg = load_profiles()
    mix = use_case_mix(req)
    shares: dict[str, list[float]] = {}
    weights: dict[str, float] = {}
    gpu_required = False
    min_ram = cfg["defaults"]["min_ram_gb"]
    min_sto = cfg["defaults"]["min_storage_gb"]
    for uc, w in mix.items():
        p = cfg["profiles"][uc]
        for cat, (sh, tol) in p["shares"].items():
            cur = shares.setdefault(cat, [0.0, 0.0])
            cur[0] += w * sh
            cur[1] += w * tol
        for k, v in p["weights"].items():
            weights[k] = weights.get(k, 0.0) + w * v
        gpu_required = gpu_required or (p["gpu_required"] and w >= 0.4)
        min_ram = max(min_ram, p.get("min_ram_gb", 0) if w >= 0.4 else 0)
        min_sto = max(min_sto, p.get("min_storage_gb", 0) if w >= 0.4 else 0)
    if "gaming" in mix and budget >= 70_000:
        min_ram = max(min_ram, 32 if budget >= 100_000 else 16)
        min_sto = max(min_sto, 1000)
    res = req.gaming.resolution if req.gaming else None
    if "gaming" in mix:  # CPU matters less in 4K, more in 1080p
        k_cpu, k_gpu = {"4k": (0.6, 1.2), "1440p": (1.0, 1.0), "1080p": (1.2, 0.95)}.get(
            res or "1440p", (1.0, 1.0)
        )
        weights["cpu_g"] *= k_cpu
        weights["gpu"] *= k_gpu
    pr = req.preferences
    if pr.no_discrete_gpu:
        gpu_required = False
        g = shares["gpu"][0]
        shares["gpu"] = [0.0, 0.0]
        shares["cpu"][0] += g * 0.6
        shares["ram"][0] += g * 0.2
        shares["storage"][0] += g * 0.2
        weights["cpu_g"] += weights.pop("gpu", 0.0) * 0.5
        weights["gpu"] = 0.0
    if pr.min_ram_gb:
        min_ram = max(min_ram, pr.min_ram_gb)
    if pr.min_storage_gb:
        min_sto = max(min_sto, pr.min_storage_gb)
    total = sum(weights.values()) or 1.0
    weights = {k: v / total for k, v in weights.items()}
    ref = 32 if set(mix) <= {"gaming", "office", "study", "programming", "streaming"} else 64
    return Profile(
        {k: (v[0], v[1]) for k, v in shares.items()},
        weights,
        gpu_required,
        int(min_ram),
        int(min_sto),
        ref,
    )


def allocate(req: Requirements, budget: int) -> dict[str, float]:
    """Budget in rubles per category (used by the UI/explanations and candidate windows)."""
    prof = build_profile(req, budget)
    return {cat: round(sh * budget) for cat, (sh, _) in prof.shares.items()}
