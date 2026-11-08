"""Import BuildCores OpenDB (CC BY-NC-SA 4.0) into the components table.

Usage:
  python scripts/import_opendb.py --path /data/buildcores-open-db [--dry-run] [--limit N]
  python scripts/import_opendb.py --download          # shallow git clone into a temp dir
Path may also come from OPENDB_PATH. Re-running updates rows (no duplicates).
"""

import argparse
import asyncio
import json
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

import _common  # noqa: F401

from app.catalog.opendb_mapping import DIRS, MAPPERS, Rejected
from app.catalog.perf import PerfTable, resolve_perf
from app.config import get_settings

REPO = "https://github.com/buildcores/buildcores-open-db"


def collect(root: Path, limit: int | None = None) -> tuple[list[dict], Counter, Counter]:
    imported: Counter = Counter()
    rejected: Counter = Counter()
    rows: dict[tuple, dict] = {}
    perf = PerfTable(get_settings().perf_scores_path)
    for cat, dirname in DIRS.items():
        files = sorted((root / "open-db" / dirname).glob("*.json"))
        for i, f in enumerate(files):
            if limit and i >= limit:
                break
            try:
                m = MAPPERS[cat](json.loads(f.read_text(encoding="utf-8")))
            except Rejected as r:
                rejected[(cat, r.reason)] += 1
                continue
            except (ValueError, KeyError) as exc:
                rejected[(cat, f"bad_file:{type(exc).__name__}")] += 1
                continue
            key = (cat, m.brand, m.model)
            if key in rows:
                rejected[(cat, "duplicate_key")] += 1
                continue
            row = m.as_row()
            pf = resolve_perf(perf, cat, m.model, m.specs.get("chipset"), m.specs)
            if pf:
                row.update(
                    perf_score=pf.score, perf_multicore=pf.multicore, perf_estimated=pf.estimated
                )
            rows[key] = row
            imported[cat] += 1
    return list(rows.values()), imported, rejected


def print_stats(imported: Counter, rejected: Counter) -> None:
    print("== imported ==")
    for cat in DIRS:
        print(f"  {cat:12s} {imported[cat]}")
    print("== rejected (category, reason) ==")
    for (cat, reason), n in sorted(rejected.items()):
        print(f"  {cat:12s} {reason:32s} {n}")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path")
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    path = a.path or get_settings().opendb_path
    tmp = None
    if a.download:
        tmp = tempfile.mkdtemp(prefix="opendb-")
        subprocess.run(
            ["git", "clone", "--depth", "1", REPO, tmp],
            check=True,
            env={"GIT_LFS_SKIP_SMUDGE": "1", "PATH": "/usr/bin:/bin"},
        )
        path = tmp
    if not path:
        raise SystemExit("give --path, --download or set OPENDB_PATH")
    rows, imported, rejected = collect(Path(path), a.limit)
    print_stats(imported, rejected)
    if a.dry_run:
        print("dry run: nothing written")
        return
    from app.catalog.db_writer import upsert_components
    from app.db.session import get_engine, get_session_maker

    get_engine()
    async with get_session_maker()() as session:
        ins, upd = await upsert_components(session, rows)
    print(f"db: {ins} inserted, {upd} updated")
    print(
        "NOTE: OpenDB has no prices; run scripts/import_prices.py, otherwise nothing is "
        "purchasable and the recommender will skip these components."
    )


if __name__ == "__main__":
    asyncio.run(main())
