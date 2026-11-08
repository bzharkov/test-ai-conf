"""Build scoring (TZ 8.5)."""

from __future__ import annotations

import math

from app.domain import Build
from app.llm.schemas import Requirements
from app.recommender.budget import Profile

IGPU_BASELINE = 0.04


def gpu_norm(build: Build) -> float:
    if build.gpu is None:
        return IGPU_BASELINE if build.cpu is not None and build.cpu.spec("has_igpu") else 0.0
    return (build.gpu.perf_score or 0.0) / 100.0


def terms(build: Build, prof: Profile) -> dict[str, float]:
    t: dict[str, float] = {}
    if build.gpu is not None or build.cpu is not None:
        t["gpu"] = math.sqrt(gpu_norm(build))
    if build.cpu is not None:
        t["cpu_g"] = (build.cpu.perf_score or 0.0) / 100.0
        t["cpu_m"] = (build.cpu.perf_multicore or 0.0) / 100.0
    if build.ram is not None:
        t["ram"] = min(1.0, float(build.ram.spec("capacity_gb_total") or 0) / prof.ram_ref_gb)
    if build.storage:
        d = build.storage[0]
        cap = min(1.0, float(d.spec("capacity_gb") or 0) / 2000.0)
        t["storage"] = 0.7 * cap + (
            0.3 if d.spec("type") == "nvme" else 0.1 if d.spec("type") == "sata_ssd" else 0.0
        )
        if d.spec("type") == "hdd":
            t["storage"] *= 0.3
    return t


def bottleneck_penalty(build: Build, req: Requirements) -> float:
    if build.cpu is None or build.gpu is None or "gaming" not in req.use_cases:
        return 0.0
    res = req.gaming.resolution if req.gaming else None
    gpu_t = math.sqrt((build.gpu.perf_score or 0) / 100.0)
    cpu_t = (build.cpu.perf_score or 0) / 100.0
    allow_gpu_over = {"4k": 0.30, "1440p": 0.20, "1080p": 0.12}.get(res or "1440p", 0.2)
    over_cpu = gpu_t - cpu_t - allow_gpu_over  # CPU too weak for the GPU
    over_gpu = cpu_t - gpu_t - 0.40  # GPU much weaker than the CPU
    return 0.6 * max(0.0, over_cpu, over_gpu)


def skew_penalty(build: Build, prof: Profile) -> float:
    total = build.total_price
    if total <= 0:
        return 0.0
    by_cat: dict[str, float] = {}
    for c in build.components():
        by_cat[c.category] = by_cat.get(c.category, 0.0) + (c.price_rub or 0.0)
    pen = 0.0
    for cat, (share, tol) in prof.shares.items():
        if share == 0:
            continue
        w = 1.5 if cat in ("gpu", "cpu") else 0.3
        pen += w * max(0.0, abs(by_cat.get(cat, 0.0) / total - share) - tol - 0.03)
    return pen


def score_build(
    build: Build,
    req: Requirements,
    prof: Profile,
    budget: int,
    w_value: float = 0.15,
    n_warnings: int = 0,
) -> float:
    t = terms(build, prof)
    s = sum(prof.weights.get(k, 0.0) * v for k, v in t.items())
    if budget > 0 and build.total_price > 0:
        s += w_value * (1.0 - build.total_price / budget)
    s -= bottleneck_penalty(build, req) + skew_penalty(build, prof) + 0.02 * n_warnings
    return s


def perf_only(build: Build, prof: Profile) -> float:
    t = terms(build, prof)
    return sum(prof.weights.get(k, 0.0) * v for k, v in t.items())
