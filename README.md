# AI PC Configuration

## Запуск

```bash
cp .env.example .env      # при необходимости впишите OPENROUTER_API_KEY и LLM_MODEL
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend / OpenAPI: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health

Без ключа OpenRouter сервис работает через детерминированный fallback-парсер.

## Разработка

```bash
make check    # ruff + mypy + pytest (backend), eslint + prettier + vitest + build (frontend)
```

Backend: `cd backend && pip install -e ".[dev]"`. Frontend: `cd frontend && npm install`.

## Статус этапов

| Этап | Статус |
|---|---|
| 1. Каркас | готово |
| 2–9 | не начаты |

## Атрибуция

Характеристики комплектующих: [BuildCores OpenDB](https://github.com/buildcores/buildcores-open-db),
лицензия ODC-By 1.0 (адрес репозитория будет проверен на этапе 2).
