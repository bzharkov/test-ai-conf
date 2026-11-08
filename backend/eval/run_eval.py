"""Quality evaluation (TZ stage 8). Writes docs/EVAL_REPORT.md.

Usage: python eval/run_eval.py [--llm]   (--llm needs OPENROUTER_API_KEY + LLM_MODEL)
Modes: 'fallback' = regex parser + template explanations; 'llm' = real model if configured."""

import argparse
import asyncio
import statistics
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.catalog.repository import Catalog, build_seed_components  # noqa: E402
from app.compat import check_build, has_errors  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.core.builds import BuildView, hydrate, to_stored  # noqa: E402
from app.llm.client import get_llm  # noqa: E402
from app.llm.explain import explanation_events  # noqa: E402
from app.llm.parser import parse_requirements  # noqa: E402
from app.llm.validator import STATS, Vocabulary, find_violations  # noqa: E402
from app.recommender.service import recommend  # noqa: E402


def check_expect(rec, res, exp: dict) -> list[str]:
    b, fails = rec.build, []
    if "dgpu" in exp and (b.gpu is not None) != exp["dgpu"]:
        fails.append(f"dgpu!={exp['dgpu']}")
    if exp.get("min_ram") and (b.ram.spec("capacity_gb_total") < exp["min_ram"]):
        fails.append("ram")
    if exp.get("min_gpu_perf") and ((b.gpu.perf_score if b.gpu else 0) < exp["min_gpu_perf"]):
        fails.append("gpu_perf")
    if exp.get("min_cpu_multi") and ((b.cpu.perf_multicore or 0) < exp["min_cpu_multi"]):
        fails.append("cpu_multi")
    if exp.get("min_cpu_gaming") and ((b.cpu.perf_score or 0) < exp["min_cpu_gaming"]):
        fails.append("cpu_gaming")
    if exp.get("compact") and "ATX" in b.case.spec("supported_mb_form_factors"):
        fails.append("compact")
    return fails


async def run(mode: str, catalog: Catalog, queries: list[dict]) -> list[dict]:
    llm = get_llm() if mode == "llm" else None
    rows = []
    for q in queries:
        exp = q["expect"]
        t0 = time.monotonic()
        req, _ = await parse_requirements(q["text"], llm, None)
        res = await asyncio.to_thread(recommend, catalog, req)
        dt = time.monotonic() - t0
        row = {
            "id": q["id"],
            "text": q["text"],
            "mode": mode,
            "time": dt,
            "n": len(res.recs),
            "compat": True,
            "budget": True,
            "task": True,
            "halluc": 0,
            "note": "",
        }
        if not res.recs:
            row.update(compat=False, budget=False, task=False, note="no build")
            rows.append(row)
            continue
        unreachable = exp.get("unreachable", False)
        top = res.recs[0]
        row["compat"] = all(not has_errors(check_build(r.build)) for r in res.recs)
        if unreachable:
            row["budget"] = res.recs[0].over_budget and any(
                w["code"] == "over_budget" for w in res.warnings
            )
            row["note"] = "ожидался over_budget"
        else:
            row["budget"] = all(r.total <= res.budget + 1e-6 for r in res.recs)
        if "has_budget" in exp:
            row["task"] = (
                (req.budget_rub is not None) == exp["has_budget"]
                or exp["has_budget"] is False
                and req.budget_assumed
            )
        fails = [] if unreachable else check_expect(top, res, exp)
        row["task"] = row["task"] and not fails
        if fails:
            row["note"] = ",".join(fails)
        # explanation hallucinations
        stored = to_stored(top, 1, res.budget)
        stored["id"] = 1
        view: BuildView = hydrate(stored, catalog)
        vocab = Vocabulary(view.build.components(), catalog.components)
        text = ""
        async for ev in explanation_events(view, req.model_dump(), catalog, llm):
            if ev["event"] == "done":
                text = ev["data"]["text"]
        row["halluc"] = len(find_violations(text, vocab))
        rows.append(row)
    return rows


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    t = sorted(r["time"] for r in rows)
    return {
        "n": n,
        "compat_errors": sum(not r["compat"] for r in rows),
        "budget_ok_pct": 100 * sum(r["budget"] for r in rows) / n,
        "task_ok_pct": 100 * sum(r["task"] for r in rows) / n,
        "halluc": sum(r["halluc"] for r in rows),
        "p50": statistics.median(t),
        "p95": t[min(n - 1, int(0.95 * n))],
    }


def table(rows: list[dict]) -> str:
    out = [
        "| ID | Запрос | Совместимость | Бюджет | Задача | Время, с | Галлюц. | Примечание |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        ok = lambda v: "✓" if v else "✗"  # noqa: E731
        out.append(
            f"| {r['id']} | {r['text']} | {ok(r['compat'])} | {ok(r['budget'])} | "
            f"{ok(r['task'])} | {r['time']:.2f} | {r['halluc']} | {r['note']} |"
        )
    return "\n".join(out)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true")
    a = ap.parse_args()
    s = get_settings()
    catalog = Catalog(build_seed_components(ROOT / s.seed_dir, ROOT / s.perf_scores_path, "csv"))
    queries = yaml.safe_load((ROOT / "eval/queries.yaml").read_text(encoding="utf-8"))["queries"]
    parts = [
        "# Отчёт об оценке качества\n",
        f"Каталог: демо ({len(catalog)} компонентов), цены ориентировочные. "
        f"Запросов: {len(queries)}.\n",
    ]
    modes = ["fallback"] + (["llm"] if a.llm and s.llm_available else [])
    for mode in modes:
        rows = await run(mode, catalog, queries)
        m = summarize(rows)
        parts.append(f"\n## Режим: {mode}\n")
        parts.append("| Метрика | Цель | Факт |\n|---|---|---|")
        parts.append(f"| Ошибки совместимости | 0 | {m['compat_errors']} |")
        parts.append(f"| Сборки в бюджете | 100 % | {m['budget_ok_pct']:.0f} % |")
        parts.append(f"| Соответствие задаче | ≥ 80 % | {m['task_ok_pct']:.0f} % |")
        parts.append(f"| Галлюцинации в объяснениях | 0 | {m['halluc']} |")
        parts.append(
            f"| Время подбора p50 / p95 | ≤ 5 / ≤ 15 с | {m['p50']:.2f} / {m['p95']:.2f} с |\n"
        )
        parts.append(table(rows))
    if not (a.llm and s.llm_available):
        parts.append(
            "\n\n> Режим `llm` не запускался: не задан `OPENROUTER_API_KEY`/`LLM_MODEL` "
            "(запуск: `python eval/run_eval.py --llm`)."
        )
    parts.append(f"\n\nСчётчики валидатора: {dict(STATS)}\n")
    out = ROOT.parent / "docs" / "EVAL_REPORT.md"
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"written {out}")


if __name__ == "__main__":
    asyncio.run(main())
