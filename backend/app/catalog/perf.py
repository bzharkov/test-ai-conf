"""Performance scores: curated CSV first, heuristic fallback marked perf_estimated."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Perf:
    score: float | None  # gpu score or cpu gaming score
    multicore: float | None
    estimated: bool


class PerfTable:
    def __init__(self, path: str | Path | None) -> None:
        self._rows: dict[str, list[tuple[re.Pattern[str], dict[str, str]]]] = {}
        if path and Path(path).exists():
            with open(path, encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    self._rows.setdefault(row["category"], []).append(
                        (re.compile(row["model_pattern"], re.I), row)
                    )

    @staticmethod
    def _num(v: str | None) -> float | None:
        return float(v) if v not in (None, "") else None

    def lookup(self, category: str, key: str) -> Perf | None:
        for pat, row in self._rows.get(category, []):
            if pat.search(key):
                if category == "cpu":
                    return Perf(
                        self._num(row["score_gaming"]), self._num(row["score_multicore"]), False
                    )
                return Perf(self._num(row["score"]), None, False)
        return None


def heuristic_cpu(specs: dict) -> Perf:
    cores, threads = specs.get("cores") or 4, specs.get("threads") or 4
    boost = specs.get("boost_clock_ghz") or 3.5
    multi = min(100.0, (cores * 0.8 + (threads - cores) * 0.25) * boost * 1.1)
    gaming = min(95.0, 25 + boost * 8 + min(cores, 8) * 2.5)
    return Perf(round(gaming, 1), round(multi, 1), True)


def heuristic_gpu(specs: dict) -> Perf:
    tdp, vram = specs.get("tdp_w") or 100, specs.get("vram_gb") or 4
    return Perf(round(min(90.0, tdp / 575 * 85 + vram * 0.6), 1), None, True)


def resolve_perf(
    table: PerfTable, category: str, model: str, chipset: str | None, specs: dict
) -> Perf | None:
    if category == "cpu":
        return table.lookup("cpu", model) or heuristic_cpu(specs)
    if category == "gpu":
        return table.lookup("gpu", chipset or model) or heuristic_gpu(specs)
    return None
