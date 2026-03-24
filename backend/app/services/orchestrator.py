"""3-stage query pipeline orchestrator.

Stage 1: Generate SQL (LangChain agent + few-shot memory)
Stage 2: Safety check (sqlglot) + EXPLAIN gate
Stage 3: Execute + GX validation + store audit log
"""

import time
import uuid
from typing import Any

import pandas as pd
import psycopg2
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import log
from app.db.models import FewShotExample, QueryLog, QueryMetrics
from app.schemas.query import (
    ExplainSummary,
    FewShotExampleOut,
    QueryRequest,
    QueryResponse,
    ValidationSummary,
)
from app.services.explain_gate import ExplainGateError, check_explain_thresholds, run_explain
from app.services.gx_validate import validate_results
from app.services.nl2sql_agent import NL2SQLGenerationError, generate_sql
from app.services.schema_context import get_schema_context
from app.services.sql_safety import SQLSafetyError, check_sql_safety


async def _resolve_target_url(
    connection_id: uuid.UUID | None, db: AsyncSession
) -> str:
    """Resolve target database URL from connection_id or fall back to settings."""
    if not connection_id:
        return settings.target_database_url

    from app.db.models import Connection

    result = await db.execute(
        select(Connection).where(Connection.id == connection_id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise ValueError(f"Connection {connection_id} not found")
    return conn.database_url


async def run_query_pipeline(request: QueryRequest, db: AsyncSession) -> QueryResponse:
    """Run the full 3-stage pipeline with self-correction loop."""
    query_id = uuid.uuid4()
    attempted_sqls: list[str] = []
    start_time = time.monotonic()

    # Resolve target connection
    try:
        target_url = await _resolve_target_url(request.connection_id, db)
    except ValueError as e:
        return QueryResponse(
            query_id=query_id,
            nl_query=request.nl_query,
            status="error",
            error=str(e),
        )

    # Compute schema context
    schema_context = get_schema_context(
        target_database_url=target_url,
        schema_ddl=request.schema_ddl,
        connection_id=str(request.connection_id) if request.connection_id else None,
    )

    # Create initial query log entry
    query_log = QueryLog(
        id=query_id,
        nl_query=request.nl_query,
        user_id=request.user_id,
        connection_id=request.connection_id,
        status="pending",
    )
    db.add(query_log)
    await db.flush()

    # Fetch few-shot examples
    few_shot = await _get_few_shot_examples(db, request.user_id)

    last_error: str | None = None
    final_sql: str | None = None
    explain_summary: dict[str, Any] | None = None
    columns: list[str] = []
    rows: list[list] = []
    validation_summary: dict[str, Any] | None = None

    for attempt in range(settings.querymind_max_retries):
        await log.ainfo("pipeline_attempt", attempt=attempt + 1, query_id=str(query_id))

        try:
            # --- Stage 1: Generate SQL ---
            error_context = ""
            if last_error and attempted_sqls:
                error_context = (
                    f"\n\nYour previous SQL attempt:\n{attempted_sqls[-1]}\n"
                    f"Failed with error: {last_error}\n"
                    f"Fix the SQL to resolve this error."
                )
            augmented_query = request.nl_query + error_context

            raw_sql = await generate_sql(
                augmented_query,
                few_shot,
                target_database_url=target_url,
                schema_context=schema_context,
            )
            attempted_sqls.append(raw_sql)

            # --- Stage 2: Safety + EXPLAIN gate ---
            safe_sql = check_sql_safety(raw_sql)
            await log.ainfo("safety_check_passed", sql=safe_sql)

            explain_summary = run_explain(safe_sql, target_database_url=target_url)
            check_explain_thresholds(explain_summary)
            await log.ainfo("explain_gate_passed", summary=explain_summary)

            # --- Stage 3: Execute + validate ---
            columns, rows, exec_ms = _execute_query(safe_sql, target_database_url=target_url)
            final_sql = safe_sql

            df = pd.DataFrame(rows, columns=columns)
            validation_summary = validate_results(df)

            # Store metrics
            total_ms = (time.monotonic() - start_time) * 1000
            query_log.final_sql = final_sql
            query_log.attempted_sqls = attempted_sqls
            query_log.explain_summary = explain_summary
            query_log.status = "success"
            query_log.row_count = len(rows)
            query_log.runtime_ms = total_ms
            query_log.validation_result = validation_summary

            metrics = QueryMetrics(
                query_log_id=query_id,
                explain_cost=explain_summary.get("total_cost"),
                explain_rows=explain_summary.get("estimated_rows"),
                execution_ms=exec_ms,
                row_count=len(rows),
            )
            db.add(metrics)
            await db.commit()

            return QueryResponse(
                query_id=query_id,
                nl_query=request.nl_query,
                final_sql=final_sql,
                columns=columns,
                rows=rows,
                row_count=len(rows),
                runtime_ms=total_ms,
                explain_summary=ExplainSummary(**{
                    k: explain_summary[k]
                    for k in ("total_cost", "estimated_rows", "plan_nodes")
                }) if explain_summary else None,
                validation_summary=ValidationSummary(**validation_summary) if validation_summary else None,
                status="success",
                attempted_sqls=attempted_sqls,
            )

        except SQLSafetyError as e:
            last_error = f"Safety violation: {e}"
            await log.awarning("safety_violation", error=last_error, attempt=attempt + 1)
        except NL2SQLGenerationError as e:
            last_error = (
                "Unsupported question for current schema: "
                f"{e}. Try asking about existing tables/columns."
            )
            await log.awarning("nl2sql_invalid_output", error=last_error, attempt=attempt + 1)
            break
        except ExplainGateError as e:
            last_error = f"Query too expensive: {e}"
            await log.awarning("explain_gate_blocked", error=last_error, attempt=attempt + 1)
            # Don't retry expensive queries — return the block immediately
            break
        except Exception as e:
            last_error = f"Execution error: {e}"
            await log.awarning("execution_error", error=last_error, attempt=attempt + 1)

    # All retries exhausted or blocked
    total_ms = (time.monotonic() - start_time) * 1000
    query_log.attempted_sqls = attempted_sqls
    query_log.status = "error"
    query_log.error = last_error
    query_log.runtime_ms = total_ms
    await db.commit()

    return QueryResponse(
        query_id=query_id,
        nl_query=request.nl_query,
        final_sql=final_sql,
        status="error",
        error=last_error,
        attempted_sqls=attempted_sqls,
        runtime_ms=total_ms,
    )


def _execute_query(
    sql: str, target_database_url: str | None = None
) -> tuple[list[str], list[list], float]:
    """Execute a query against the target database with safety constraints.

    Returns (columns, rows, execution_ms).
    """
    db_url = target_database_url or settings.target_database_url
    conn = psycopg2.connect(db_url)
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute(
                f"SET LOCAL statement_timeout = '{settings.querymind_statement_timeout}'"
            )
            start = time.monotonic()
            cur.execute(sql)
            rows = cur.fetchall()
            exec_ms = (time.monotonic() - start) * 1000

            columns = [desc[0] for desc in cur.description] if cur.description else []
            conn.rollback()  # Read-only — never commit
    finally:
        conn.close()

    # Convert rows to lists (from tuples) for JSON serialization
    return columns, [list(row) for row in rows], exec_ms


async def _get_few_shot_examples(
    db: AsyncSession, user_id: str | None
) -> list[FewShotExampleOut]:
    """Retrieve few-shot examples: user-specific + global."""
    examples: list[FewShotExample] = []

    if user_id:
        user_stmt = (
            select(FewShotExample)
            .where(FewShotExample.user_id == user_id)
            .order_by(FewShotExample.created_at.desc())
            .limit(settings.querymind_few_shot_user_k)
        )
        result = await db.execute(user_stmt)
        examples.extend(result.scalars().all())

    global_stmt = (
        select(FewShotExample)
        .where(FewShotExample.is_global.is_(True))
        .order_by(FewShotExample.created_at.desc())
        .limit(settings.querymind_few_shot_global_k)
    )
    result = await db.execute(global_stmt)
    examples.extend(result.scalars().all())

    return [FewShotExampleOut.model_validate(ex) for ex in examples]
