.PHONY: up down backend frontend test lint migrate

# Start Postgres
up:
	docker compose up -d postgres

# Stop Postgres
down:
	docker compose down

# Install backend dependencies
install-backend:
	cd backend && uv sync

# Install frontend dependencies
install-frontend:
	cd frontend && uv sync

# Install all
install: install-backend install-frontend

# Run DB migrations
migrate:
	cd backend && uv run alembic upgrade head

# Start backend (dev)
backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

# Start frontend (dev)
frontend:
	cd frontend && uv run streamlit run streamlit_app.py

# Run tests
test:
	cd backend && uv run pytest -v

# Run safety tests only
test-safety:
	cd backend && uv run pytest app/tests/test_sql_safety.py -v

# Run eval suite
eval:
	cd backend && uv run pytest app/tests/test_eval.py -v -s

# Lint
lint:
	cd backend && uv run ruff check .
