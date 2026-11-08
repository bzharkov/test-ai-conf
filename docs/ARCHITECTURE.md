# Architecture

```
frontend (React/Vite, nginx in prod) ──/api/v1──► backend (FastAPI) ──► PostgreSQL 16 + pgvector
                                                      │               └► Redis (cache, rate limit)
                                                      └► OpenRouter (only LLM; optional)
```

## Pipeline (`POST /configure`)

1. **Parse** (`llm/parser.py`): LLM returns JSON validated by `Requirements` (retry ≤ 2 with the
   validation error). Merged with the regex parser (`llm/fallback_parser.py`): explicit numbers
   (budget), resolution and model names from regex win. Cached in Redis by hash of normalized text
   (24 h). No key / LLM error → regex only + `llm_unavailable`.
2. **Budget** (`recommender/budget.py`, `profiles.yaml`): shares per category by profile; several
   use cases are mixed (primary 0.6, the rest share 0.4).
3. **Candidates + beam search** (`recommender/engine.py`): per category only purchasable parts
   (price + in stock) with all critical fields; preferences as filters; beam search with the hard
   rules from `compat/` applied at every step, plus an exact lower bound of the remaining cost
   (cheapest *compatible* parts), so dead branches are cut early.
4. **Scoring** (`recommender/scoring.py`): weighted perf terms + value term − penalties
   (CPU/GPU bottleneck by resolution, budget skew, warnings).
5. **Variants** (`recommender/service.py`): three searches (value-oriented ≤ 80 % budget,
   balanced, perf-only) → "Оптимальная", "Экономичная", "Максимум"; each must differ from the
   others in ≥ 2 key components (CPU, GPU, RAM, storage, motherboard).
6. **Power** (`power/calc.py`): breakdown shown to the user; coefficients in `config.py`.
7. **Explanation** (`llm/explain.py`): the model sees only the build JSON + requirements.
   Output goes through the validator.

Nothing in 2–6 uses the LLM, so the recommendation is deterministic for the same catalog and
requirements and never waits for the model. If nothing fits the budget the cheapest valid build is
returned with `over_budget` and the message "ближайшая возможная сборка стоит X ₽".

## Anti-hallucination (`llm/validator.py`)

Mentions (`RTX 4070 Ti`, `Ryzen 7 7800X3D`, `Core i5-12400F`, `RX 7800 XT`, …) and model-like
tokens (`RM850e`, `AK400`) are extracted and compared with the vocabulary of the build (+ analogs
shown in chat). A violation → one regeneration with the banned list → otherwise the offending
sentences are removed with a note. Streaming: tokens are streamed live, and if validation changes
the text the server sends a `replace` event with the corrected text, then `done`.
Counters are in `validator.STATS` and in the eval report.

## Chat and analogs

`llm/chat.py`: intent classification (keywords first, a short LLM call if unclear) → backend
functions (`find_alternatives`) → streamed answer. Tool calling is intentionally not used, so any
OpenRouter model works (the TZ allows the classify-first path). `rag/alternatives.py` ranks
same-category parts by embedding similarity + intent filter (cheaper / better / similar), puts
each into the build and runs **all** compat rules. If only the PSU is insufficient, a PSU upgrade
is attached to the analog (price delta includes it). "Применить" calls `POST /builds/{id}/replace`.

## Data

`components` (specs JSONB, perf, price, embedding vector(384)), `requests`, `builds`,
`chat_messages`. The recommender works on an immutable in-memory snapshot of the catalog loaded
from the DB (seed files if the DB is empty/unreachable). Builds are persisted by `PgStore`, or by
an in-memory store when the DB is unavailable.

## Deliberate deviations from the TZ

- Beam order is GPU-first when the profile weights the GPU above the CPU (otherwise early
  expensive CPUs consume the budget and strong GPUs never fit). Otherwise the TZ order is used.
- Tool calling replaced by classify-then-call (see above).
- Embeddings: e5-small when `sentence-transformers` is installed (Docker image); otherwise a
  deterministic hash-n-gram vectorizer (not an LLM) so the project works offline.
- `perf_multicore` column added next to `perf_score` (CPU gaming score vs multicore score).
- HDD-only builds are never produced (a single drive must be an SSD).

## Design decisions (frontend)

"Technical" look: 1 px hairline borders, monospace uppercase labels, flat panels over a faint
32 px grid, a single teal accent; light/dark follows the system theme (CSS variables). Numbers are
monospace. Tables collapse into stacked rows on mobile; every grid uses `minmax(0,1fr)` so nothing
causes horizontal scroll at 360 px. Markdown is rendered by a tiny safe renderer (no `innerHTML`).
