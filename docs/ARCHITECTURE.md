# Architecture

Сервисы: `frontend` (Vite/React) → `backend` (FastAPI) → `db` (PostgreSQL 16 + pgvector), `redis`.
LLM — только облачный OpenRouter; эмбеддинги считаются на CPU внутри backend.
Пайплайн подбора и дизайн-решения будут описаны по мере реализации этапов 2–9.
