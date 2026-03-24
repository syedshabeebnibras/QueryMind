# QueryMind

Natural-language-to-SQL with self-correction, safety enforcement, and result validation.

## Quick Start

```bash
# 1. Start Postgres
docker compose up -d postgres

# 2. Set environment
cp .env.example .env
# Edit .env with your OPENAI_API_KEY and database credentials

# 3. Install dependencies
cd backend && uv sync
cd ../frontend && uv sync

# 4. Run migrations
cd backend && uv run alembic upgrade head

# 5. Start backend
cd backend && uv run uvicorn app.main:app --reload --port 8000

# 6. Start frontend (new terminal)
cd frontend && uv run streamlit run streamlit_app.py
```

## Architecture

```
┌─────────────┐     httpx      ┌─────────────────────────────────────┐
│  Streamlit   │ ──────────────▶│  FastAPI Backend                    │
│  (port 8501) │◀──────────────│  (port 8000)                        │
└─────────────┘                │                                     │
                               │  POST /query → 3-Stage Loop:        │
                               │   1. LangChain NL→SQL + few-shot    │
                               │   2. sqlglot safety + EXPLAIN gate   │
                               │   3. Execute + GX validate          │
                               │                                     │
                               │  GET  /history                      │
                               │  POST /feedback                     │
                               │  GET  /examples                     │
                               │  GET  /health                       │
                               └──────────┬──────────────────────────┘
                                          │
                               ┌──────────▼──────────┐
                               │   PostgreSQL 16      │
                               │                      │
                               │  App DB (metadata):  │
                               │   query_log          │
                               │   feedback           │
                               │   few_shot_examples  │
                               │   query_metrics      │
                               │                      │
                               │  Target DB (queries):│
                               │   (user's data)      │
                               └─────────────────────┘
```

## Safety

- **SELECT-only**: sqlglot AST allowlist blocks DDL/DML
- **Single statement**: Multi-statement batches rejected
- **LIMIT enforcement**: Default cap of 1000 rows
- **EXPLAIN gating**: Blocks queries exceeding cost/row thresholds
- **Read-only role**: DB user has minimal privileges
- **Statement timeout**: 30s default via `SET LOCAL statement_timeout`
- **Full audit log**: Every attempt logged with timing, EXPLAIN, validation

## Database Schema

| Table | Purpose |
|-------|---------|
| `query_log` | Audit trail: NL input, attempted SQLs, final SQL, EXPLAIN, timing, validation |
| `feedback` | User corrections: rating, corrected SQL, notes |
| `few_shot_examples` | Adaptive few-shot memory for prompt engineering |
| `query_metrics` | Per-query performance: EXPLAIN cost, rows, execution time |

## Evaluation

```bash
cd backend && uv run pytest app/tests/test_eval.py -v
```

Load test cases from `backend/eval_suite.json` — NL questions with expected SQL or result checks.
