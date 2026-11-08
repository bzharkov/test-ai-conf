"""Candidate selection + beam search (TZ 8.3, 8.4)."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from app.catalog.repository import Catalog
from app.compat import check_build
from app.config import get_settings
from app.domain import Build, Component
from app.llm.schemas import Requirements
from app.power.calc import calculate_power
from app.recommender import scoring
from app.recommender.budget import Profile

ORDER = ["cpu", "motherboard", "ram", "gpu", "cpu_cooler", "case", "psu", "storage"]
# Deviation from the TZ order: when the GPU matters more than the CPU for the profile it is
# decided first, otherwise early expensive CPUs eat the budget and strong GPUs never fit.
ORDER_GPU_FIRST = ["gpu", "cpu", "motherboard", "ram", "cpu_cooler", "case", "psu", "storage"]
BRANCH = {
    "cpu": 10,
    "motherboard": 4,
    "ram": 3,
    "gpu": 8,
    "cpu_cooler": 3,
    "case": 3,
    "psu": 3,
    "storage": 4,
}
EFF_RANK = {
    "80+": 0,
    "80+ Bronze": 1,
    "80+ Silver": 1.5,
    "80+ Gold": 2,
    "80+ Platinum": 3,
    "80+ Titanium": 4,
}


def gpu_vendor(c: Component) -> str:
    t = f"{c.specs.get('chipset', '')} {c.name}".lower()
    if "geforce" in t or "rtx" in t or "gtx" in t:
        return "nvidia"
    if "radeon" in t or " rx " in f" {t} ":
        return "amd"
    if "arc" in t:
        return "intel"
    return "other"


@dataclass
class Constraints:
    req: Requirements
    prof: Profile
    forced: dict[str, Component] = field(default_factory=dict)
    soft_prefs: bool = True  # brand / wifi / form factor / storage-size preferences
    gpu_mode: str = "required"  # required | optional | none


@dataclass
class SearchConfig:
    cap: float  # hard price cap for this search (inf for min-cost fallback)
    budget: int  # reference budget for value term / shares
    w_value: float = 0.15
    mode: str = "score"  # "score" | "perf" | "min_cost"
    beam_width: int = 40
    time_limit_s: float = 4.0


def eligible_pool(catalog: Catalog, cat: str, cons: Constraints) -> list[Component]:
    req, pr = cons.req, cons.req.preferences
    out: list[Component] = []
    excl = [e.lower() for e in req.exclude]
    forced = cons.forced.get(cat)
    for c in catalog.by_category.get(cat, []):
        if not c.purchasable or c.missing_critical():
            continue
        if forced is not None and c.id != forced.id:
            continue
        if any(e in c.name.lower() for e in excl):
            continue
        s = c.specs
        if cat == "ram" and s["capacity_gb_total"] < cons.prof.min_ram_gb:
            continue
        if cat == "storage" and s["type"] == "hdd":
            continue  # single-drive builds need an SSD as system disk
        if cat == "storage" and s["capacity_gb"] < min(
            cons.prof.min_storage_gb, 500 if not cons.soft_prefs else 10**9
        ):
            continue
        if forced is None and cons.soft_prefs:
            if cat == "cpu" and pr.cpu_brand != "any" and pr.cpu_brand not in c.brand.lower():
                continue
            if cat == "gpu" and pr.gpu_brand != "any" and gpu_vendor(c) != pr.gpu_brand:
                continue
            if cat == "motherboard":
                if pr.wifi_required and not s.get("wifi"):
                    continue
                if pr.form_factor == "mini_itx" and s["form_factor"] != "Mini-ITX":
                    continue
                if pr.form_factor == "compact" and s["form_factor"] == "ATX":
                    continue
            if cat == "case":
                sup = s["supported_mb_form_factors"]
                if pr.form_factor == "mini_itx" and sup != ["Mini-ITX"]:
                    continue
                if pr.form_factor == "compact" and "ATX" in sup:
                    continue
        out.append(c)
    return sorted(out, key=lambda c: c.id)


def quick_ok(b: Build, c: Component) -> bool:
    """Cheap pre-filters that mirror the hard rules, before running the full rule set."""
    s = c.specs
    cat = c.category
    if cat == "motherboard" and b.cpu:
        return s["socket"] == b.cpu.spec("socket") and s["memory_type"] in b.cpu.spec(
            "memory_types"
        )
    if cat == "ram":
        if b.motherboard and s["type"] != b.motherboard.spec("memory_type"):
            return False
        return b.cpu is None or s["type"] in b.cpu.spec("memory_types")
    if cat == "cpu_cooler":
        if b.cpu and b.cpu.spec("socket") not in s["sockets"]:
            return False
        if b.case:
            if s["type"] == "air":
                return (s.get("height_mm") or 0) <= b.case.spec("max_cooler_height_mm")
            return s.get("radiator_mm") in (b.case.spec("radiator_support_mm") or [])
        return True
    if cat == "case":
        if (
            b.motherboard
            and b.motherboard.spec("form_factor") not in s["supported_mb_form_factors"]
        ):
            return False
        if b.gpu is not None and b.gpu.spec("length_mm") > s["max_gpu_length_mm"]:
            return False
        if b.cpu_cooler is not None:
            ck = b.cpu_cooler.specs
            if ck["type"] == "air" and (ck.get("height_mm") or 0) > s["max_cooler_height_mm"]:
                return False
            if ck["type"] == "aio" and ck.get("radiator_mm") not in (
                s.get("radiator_support_mm") or []
            ):
                return False
        return True
    if cat == "psu" and b.case:
        pf, cf = s["form_factor"], b.case.spec("psu_form_factor")
        return pf == cf or (pf == "SFX" and cf == "ATX")
    if cat == "gpu" and b.case:
        return s["length_mm"] <= b.case.spec("max_gpu_length_mm")
    return True


def _quality(c: Component, cons: Constraints) -> float:
    w, s = cons.prof.weights, c.specs
    if c.category == "cpu":
        return (
            w.get("cpu_g", 0) * (c.perf_score or 0) / 100
            + w.get("cpu_m", 0) * (c.perf_multicore or 0) / 100
        )
    if c.category == "gpu":
        return (c.perf_score or 0) / 100
    if c.category == "ram":
        return s["capacity_gb_total"] / cons.prof.ram_ref_gb + (s.get("speed_mhz") or 0) / 40000
    if c.category == "storage":
        return min(1.0, s["capacity_gb"] / 2000) + (0.3 if s["type"] == "nvme" else 0.0)
    if c.category == "psu":
        return EFF_RANK.get(s.get("efficiency") or "", 0) + (0.5 if s.get("modular") else 0)
    return c.price_rub or 0.0  # motherboard / case / cooler: price is the tier proxy


def _no_missing(issues) -> bool:
    return not any(i.severity == "error" or i.code == "MISSING_DATA" for i in issues)


class Searcher:
    def __init__(self, catalog: Catalog, cons: Constraints) -> None:
        self.cons = cons
        w = cons.prof.weights
        gpu_first = cons.gpu_mode != "none" and w.get("gpu", 0) >= w.get("cpu_g", 0) + w.get(
            "cpu_m", 0
        )
        self.order = ORDER_GPU_FIRST if gpu_first else ORDER
        self.pools = {cat: eligible_pool(catalog, cat, cons) for cat in ORDER}
        self.min_price = {
            cat: min((c.price_rub or 0 for c in p), default=math.inf)
            for cat, p in self.pools.items()
        }
        if cons.gpu_mode == "none":
            igpu = [c for c in self.pools["cpu"] if c.spec("has_igpu")]
            if igpu:
                self.pools["cpu"] = igpu
            self.pools["gpu"] = []
        if cons.gpu_mode != "required":
            self.min_price["gpu"] = 0.0
        self.min_price["cpu"] = min((c.price_rub or 0 for c in self.pools["cpu"]), default=math.inf)

    def _allow_no_gpu(self, b: Build) -> bool:
        return self.cons.gpu_mode != "required" and bool(b.cpu and b.cpu.spec("has_igpu"))

    def _cap_price(self, cat: str, cfg: SearchConfig) -> float:
        share = self.cons.prof.shares.get(cat, (0.05, 0.02))[0]
        mult = 2.2 if cat in ("cpu", "gpu") else 1.8
        return max(share, 0.03) * cfg.budget * mult

    def _min_compatible(self, b: Build, cat: str) -> float:
        """Cheapest component of `cat` that is quick-compatible with the partial build."""
        need = calculate_power(b, extra_w=10).psu_recommended_w if cat == "psu" else 0
        best = math.inf
        for c in self.pools[cat]:
            p = c.price_rub or 0
            if p >= best or not quick_ok(b, c):
                continue
            if cat == "psu" and c.specs["wattage_w"] < need:
                continue
            best = p
        return best

    def _lower_bound(self, b: Build, cat: str) -> float:
        rest = self.order[self.order.index(cat) + 1 :]
        total = 0.0
        for r in rest:
            if (
                r == "gpu"
                and (self.cons.gpu_mode != "required")
                and b.cpu is not None
                and (b.cpu.spec("has_igpu"))
            ):
                continue
            total += self._min_compatible(b, r)
        return total

    def _options(
        self, b: Build, cat: str, cfg: SearchConfig, used: float
    ) -> list[Component | None]:
        remaining_loose = sum(self.min_price[c] for c in self.order[self.order.index(cat) + 1 :])
        room = cfg.cap - used - remaining_loose
        pool = [c for c in self.pools[cat] if quick_ok(b, c) and (c.price_rub or 0) <= room]
        if cat == "psu":
            need = calculate_power(b, extra_w=10).psu_recommended_w
            pool = [c for c in pool if c.specs["wattage_w"] >= need]
        k = BRANCH[cat]
        cap_p = self._cap_price(cat, cfg)
        within = [c for c in pool if (c.price_rub or 0) <= cap_p]
        base = within or sorted(pool, key=lambda c: (c.price_rub, c.id))[:2]
        by_q = sorted(base, key=lambda c: (-_quality(c, self.cons), c.id))
        by_v = sorted(
            base, key=lambda c: (-_quality(c, self.cons) / math.sqrt(c.price_rub or 1), c.id)
        )
        cheap = sorted(pool, key=lambda c: (c.price_rub, c.id))[:2]
        priority: list[Component] = []
        half = math.ceil(k / 2)
        for i in range(max(len(by_q), len(by_v))):
            for lst in (by_q, by_v):
                if i < len(lst) and lst[i] not in priority:
                    priority.append(lst[i])
        priority += [c for c in cheap if c not in priority]
        good: list[Component] = []
        n_q = n_v = 0
        for c in priority:
            if len(good) >= k + 2:
                break
            nb = b.with_component(c)
            if not _no_missing(check_build(nb, partial=True)):
                continue
            if used + (c.price_rub or 0) + self._lower_bound(nb, cat) > cfg.cap:
                continue
            good.append(c)
        del half, n_q, n_v
        opts: list[Component | None] = list(good)
        if cat == "gpu" and self._allow_no_gpu(b):
            opts.append(None)
        return opts

    def _rank(self, b: Build, cfg: SearchConfig) -> tuple:
        if cfg.mode == "min_cost":
            return (b.total_price, tuple(c.id for c in b.components()))
        w_value = 0.0 if cfg.mode == "perf" else cfg.w_value
        s = scoring.score_build(b, self.cons.req, self.cons.prof, cfg.budget, w_value)
        return (-s, b.total_price, tuple(c.id for c in b.components()))

    def run(self, cfg: SearchConfig) -> list[Build]:
        t0 = time.monotonic()
        states: list[Build] = [Build()]
        per_group = max(2, cfg.beam_width // 3)
        for cat in self.order:
            nxt: list[Build] = []
            for b in states:
                if time.monotonic() - t0 > cfg.time_limit_s and nxt:
                    break
                for opt in self._options(b, cat, cfg, b.total_price):
                    if opt is None:
                        nxt.append(b)  # no discrete GPU
                    elif cat == "storage":
                        nxt.append(Build(**{**b.__dict__, "storage": [opt]}))
                    else:
                        nxt.append(b.with_component(opt))
            nxt.sort(key=lambda b: self._rank(b, cfg))
            states = self._diversify(nxt, cfg.beam_width, per_group)
            if not states:
                return []
        final = []
        for b in states:
            if b.total_price <= cfg.cap and _no_missing(check_build(b)):
                final.append(b)
        return sorted(final, key=lambda b: self._rank(b, cfg))

    @staticmethod
    def _diversify(sorted_states: list[Build], width: int, per_group: int) -> list[Build]:
        out: list[Build] = []
        n_cpu: dict[int, int] = {}
        n_gpu: dict[int, int] = {}
        for b in sorted_states:
            ck = b.cpu.id if b.cpu else 0
            gk = b.gpu.id if b.gpu else 0
            if n_cpu.get(ck, 0) >= per_group or n_gpu.get(gk, 0) >= per_group:
                continue
            n_cpu[ck] = n_cpu.get(ck, 0) + 1
            n_gpu[gk] = n_gpu.get(gk, 0) + 1
            out.append(b)
            if len(out) >= width:
                break
        return out


def default_config(budget: int, cap: float, **kw) -> SearchConfig:
    s = get_settings()
    return SearchConfig(
        cap=cap, budget=budget, beam_width=s.beam_width, time_limit_s=s.beam_time_limit_s, **kw
    )
