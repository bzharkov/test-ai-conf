# API (prefix `/api/v1`)

Source of truth: OpenAPI at `/docs` (`backend/openapi.json`; TS types in
`frontend/src/api/schema.d.ts`, regenerate with `npm run gen:api`). Errors:
`{"error": {"code", "message"}}` (409 `incompatible` also carries `issues`).

| Method | Path | Purpose |
|---|---|---|
| POST | `/configure` | `{text, filters?, requirements?, session_id}` → `{request_id, requirements, builds[], warnings[], min_feasible_price?}` |
| GET | `/builds/{id}` | components, compatibility (per-rule status + issues), power breakdown, explanation |
| GET | `/builds/{id}/explanation/stream` | SSE: `token`, `replace`, `done`, `error` (cached after first generation) |
| POST | `/builds/{id}/replace` | `{category, component_id, extra_component_id?}` → new build; 409 if incompatible |
| GET | `/builds/{id}/alternatives?category=&intent=cheaper\|better\|similar` | analogs without chat |
| POST | `/builds/{id}/chat` | `{message}` → SSE: `alternatives`, `token`, `replace`, `done`, `error` |
| GET | `/builds/{id}/chat` | chat history |
| POST | `/compare` | `{build_ids: [2..3]}` → table |
| GET | `/components?category=&q=&limit=` · `/components/{id}` | catalog |
| GET | `/history?session_id=` | recent requests and builds |
| GET | `/health` | DB, Redis, LLM, catalog size/source |

`filters`: `budget_rub, wifi, compact, cpu_brand (amd|intel), no_gpu`. Rate limit (Redis, falls back
to memory): 20 requests/min per `session_id` on `/configure` and `/chat` → 429 `rate_limited`.
Warning codes: `llm_unavailable, budget_assumed, over_budget, must_include_not_found,
must_include_dropped, preferences_relaxed, weak_for_4k, igpu_only, well_under_budget, no_build`.
