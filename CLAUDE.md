# QueryMind — CLAUDE.md

## Project Overview
Natural-language-to-SQL application with self-correction loop, safety enforcement, and result validation.

## Architecture
- **Frontend**: Streamlit (port 8501) → httpx → FastAPI
- **Backend**: FastAPI (port 8000) with 3-stage query loop
- **Database**: PostgreSQL (port 5432) — single infrastructure dependency
- **LLM**: LangChain SQL agent/toolkit for NL→SQL generation

## 3-Stage Query Loop
1. **Generate**: LangChain SQL agent produces SQL from NL + few-shot examples
2. **Validate & Gate**: sqlglot AST safety (SELECT-only), EXPLAIN cost/row gating
3. **Execute & Validate**: Run query, GX validation on DataFrame, store audit log

## Key Commands
```bash
# Start infrastructure
docker compose up -d postgres

# Run backend
cd backend && uv run uvicorn app.main:app --reload --port 8000

# Run frontend
cd frontend && uv run streamlit run streamlit_app.py

# Run tests
cd backend && uv run pytest

# Run DB migrations
cd backend && uv run alembic upgrade head

# Lint
uv run ruff check .
```

## Database Schema
- `query_log`: Full audit trail (NL input, all attempted SQLs, final SQL, EXPLAIN, timing, validation)
- `feedback`: User corrections (rating, corrected SQL, notes)
- `few_shot_examples`: Adaptive few-shot memory for prompt injection
- `query_metrics`: Per-query performance metrics (EXPLAIN cost, rows, execution time)

## Safety Rules (NEVER bypass)
1. SELECT-only enforcement via sqlglot AST parsing — no DDL/DML
2. Single statement only — no multi-statement batches
3. Service-enforced LIMIT cap (default 1000) unless aggregate
4. Dedicated read-only DB role with statement_timeout
5. Never concatenate user input into SQL
6. Full audit logging of every query attempt

## Threat Model
- **SQL Injection**: Mitigated by sqlglot AST parsing (not string matching)
- **Resource Exhaustion**: EXPLAIN gate blocks expensive queries; statement_timeout as backstop
- **Data Exfiltration**: Read-only role, LIMIT enforcement, no COPY/pg_read_file
- **Prompt Injection**: Few-shot examples are system-controlled, not user-injected raw text
- **Multi-statement Attacks**: sqlglot parse rejects multiple statements

## Tech Stack
- Python 3.11+, uv for package management
- FastAPI, SQLAlchemy 2.0, Alembic
- LangChain (langchain-community, langchain-openai)
- sqlglot for SQL AST parsing
- Great Expectations (GX Core) for result validation
- Streamlit + httpx for frontend
- PostgreSQL 16

## Environment Variables (in .env)
- DATABASE_URL: PostgreSQL connection for app metadata
- TARGET_DATABASE_URL: PostgreSQL connection for user queries (read-only role)
- OPENAI_API_KEY: For LLM
- QUERYMIND_STATEMENT_TIMEOUT: Default 30000 (ms)
- QUERYMIND_MAX_ROWS: Default 1000
- QUERYMIND_MAX_EXPLAIN_COST: Default 100000
- QUERYMIND_MAX_EXPLAIN_ROWS: Default 500000
