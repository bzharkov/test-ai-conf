.PHONY: check backend-check frontend-check up
check: backend-check frontend-check

backend-check:
	cd backend && ruff check . && ruff format --check . && mypy app && pytest -q

frontend-check:
	cd frontend && npm run lint && npm run format:check && npm test && npm run build

up:
	docker compose up --build
