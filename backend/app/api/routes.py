import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import log
from app.db.models import Connection, Feedback, FewShotExample, QueryLog
from app.db.session import get_db
from app.schemas.query import (
    ConnectionCreate,
    ConnectionOut,
    FeedbackRequest,
    FeedbackResponse,
    FewShotExampleOut,
    HealthResponse,
    QueryHistoryItem,
    QueryHistoryResponse,
    QueryRequest,
    QueryResponse,
    SchemaSetupRequest,
    SchemaSetupResponse,
    TableDataRequest,
    TableDataResponse,
)
from app.services.orchestrator import run_query_pipeline
from app.services.schema_setup import SchemaSetupError, execute_setup_sql
from app.services.table_parser import TableParseError, parse_table_data, parse_table_to_sql

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """Health check — verifies DB connectivity."""
    try:
        await db.execute(text("SELECT 1"))
        return HealthResponse(status="ok", database="ok")
    except Exception as exc:
        await log.awarning("health_check_failed", error=str(exc))
        return HealthResponse(status="degraded", database="error")


# --- Connection management ---


@router.get("/connections", response_model=list[ConnectionOut])
async def list_connections(
    db: AsyncSession = Depends(get_db),
) -> list[ConnectionOut]:
    """List all available target database connections."""
    result = await db.execute(
        select(Connection).order_by(Connection.created_at.desc())
    )
    return [ConnectionOut.model_validate(c) for c in result.scalars().all()]


@router.post("/connections", response_model=ConnectionOut, status_code=201)
async def create_connection(
    request: ConnectionCreate,
    db: AsyncSession = Depends(get_db),
) -> ConnectionOut:
    """Add a new target database connection."""
    # Validate it's a PostgreSQL URL
    if not request.database_url.startswith(("postgresql://", "postgres://")):
        raise HTTPException(
            status_code=400,
            detail="Only PostgreSQL connection URLs are supported.",
        )

    conn = Connection(
        name=request.name,
        database_url=request.database_url,
        owner_user_id=request.owner_user_id,
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)
    await log.ainfo("connection_created", name=conn.name, id=str(conn.id))
    return ConnectionOut.model_validate(conn)


@router.delete("/connections/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a target database connection."""
    result = await db.execute(
        select(Connection).where(Connection.id == connection_id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    await db.delete(conn)
    await db.commit()
    await log.ainfo("connection_deleted", id=str(connection_id))


# --- Table import (raw data → DB) ---


@router.post("/table/import", response_model=TableDataResponse)
async def import_table(
    request: TableDataRequest,
    db: AsyncSession = Depends(get_db),
) -> TableDataResponse:
    """Import raw table data (markdown, CSV, TSV) into the target database.

    Uses bulk insert (execute_values) for fast imports of large datasets.
    """
    import psycopg2
    from psycopg2.extras import execute_values

    from app.services.schema_setup import _get_write_url

    # Resolve target URL
    target_url: str | None = None
    if request.connection_id:
        result = await db.execute(
            select(Connection).where(Connection.id == request.connection_id)
        )
        conn = result.scalar_one_or_none()
        if not conn:
            raise HTTPException(status_code=404, detail="Connection not found")
        target_url = conn.database_url

    try:
        # Parse into structured data (no SQL string generation)
        table_name, headers, col_types, rows = parse_table_data(
            request.table_data, request.table_name
        )

        # Build CREATE TABLE DDL
        col_defs = ", ".join(f"{h} {t}" for h, t in zip(headers, col_types))
        create_sql = f"CREATE TABLE {table_name} ({col_defs})"
        drop_sql = f"DROP TABLE IF EXISTS {table_name} CASCADE"

        # Bulk insert using execute_values
        db_url = _get_write_url(target_url or settings.target_database_url)
        pg_conn = psycopg2.connect(db_url)
        try:
            pg_conn.autocommit = False
            with pg_conn.cursor() as cur:
                cur.execute(drop_sql)
                cur.execute(create_sql)

                col_list = ", ".join(headers)
                placeholders = ", ".join(["%s"] * len(headers))
                insert_sql = f"INSERT INTO {table_name} ({col_list}) VALUES %s"
                execute_values(cur, insert_sql, rows, page_size=1000)

            pg_conn.commit()
        except Exception as e:
            pg_conn.rollback()
            raise e
        finally:
            pg_conn.close()

        # Invalidate schema cache
        from app.services.schema_context import _schema_cache
        _schema_cache.clear()

        generated_sql = f"{drop_sql};\n{create_sql};\n-- {len(rows)} rows inserted via bulk import"

        await log.ainfo(
            "table_imported",
            table_name=table_name,
            columns=len(headers),
            rows=len(rows),
        )
        return TableDataResponse(
            status="success",
            table_name=table_name,
            columns=headers,
            row_count=len(rows),
            generated_sql=generated_sql,
        )
    except TableParseError as e:
        return TableDataResponse(status="error", error=f"Parse error: {e}")
    except Exception as e:
        return TableDataResponse(status="error", error=f"Import error: {e}")


# --- Tables listing ---


@router.get("/tables")
async def list_tables(
    connection_id: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all user tables in the target database with row counts."""
    import psycopg2

    target_url: str | None = None
    if connection_id:
        result = await db.execute(
            select(Connection).where(Connection.id == uuid.UUID(connection_id))
        )
        conn = result.scalar_one_or_none()
        if not conn:
            raise HTTPException(status_code=404, detail="Connection not found")
        target_url = conn.database_url

    db_url = target_url or settings.target_database_url
    pg_conn = psycopg2.connect(db_url)
    try:
        with pg_conn.cursor() as cur:
            cur.execute("""
                SELECT t.table_name,
                       (SELECT count(*) FROM information_schema.columns c
                        WHERE c.table_name = t.table_name AND c.table_schema = 'public') AS column_count
                FROM information_schema.tables t
                WHERE t.table_schema = 'public' AND t.table_type = 'BASE TABLE'
                ORDER BY t.table_name
            """)
            tables = []
            for row in cur.fetchall():
                tables.append({"table_name": row[0], "column_count": row[1]})
    finally:
        pg_conn.close()

    return tables


# --- Schema setup ---


@router.post("/schema/setup", response_model=SchemaSetupResponse)
async def setup_schema(
    request: SchemaSetupRequest,
    db: AsyncSession = Depends(get_db),
) -> SchemaSetupResponse:
    """Execute DDL to create tables and insert data in the target database."""
    # Resolve target URL
    target_url: str | None = None
    if request.connection_id:
        result = await db.execute(
            select(Connection).where(Connection.id == request.connection_id)
        )
        conn = result.scalar_one_or_none()
        if not conn:
            raise HTTPException(status_code=404, detail="Connection not found")
        target_url = conn.database_url

    try:
        summary = execute_setup_sql(request.ddl, target_database_url=target_url)
        await log.ainfo(
            "schema_setup_success",
            statements=summary["statements_executed"],
        )
        return SchemaSetupResponse(
            status="success",
            statements_executed=summary["statements_executed"],
            statements=summary["statements"],
        )
    except SchemaSetupError as e:
        await log.awarning("schema_setup_failed", error=str(e))
        return SchemaSetupResponse(status="error", error=str(e))


# --- Query pipeline ---


@router.post("/query", response_model=QueryResponse)
async def run_query(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
) -> QueryResponse:
    """Run the 3-stage NL→SQL pipeline."""
    await log.ainfo("query_received", nl_query=request.nl_query, user_id=request.user_id)
    result = await run_query_pipeline(request, db)
    return result


@router.get("/history", response_model=QueryHistoryResponse)
async def query_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    user_id: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> QueryHistoryResponse:
    """Paginated query history."""
    stmt = select(QueryLog).order_by(QueryLog.created_at.desc())
    count_stmt = select(func.count(QueryLog.id))

    if status:
        stmt = stmt.where(QueryLog.status == status)
        count_stmt = count_stmt.where(QueryLog.status == status)
    if user_id:
        stmt = stmt.where(QueryLog.user_id == user_id)
        count_stmt = count_stmt.where(QueryLog.user_id == user_id)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    items = [QueryHistoryItem.model_validate(row) for row in result.scalars().all()]

    return QueryHistoryResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    """Store user feedback on a query result."""
    feedback = Feedback(
        query_log_id=request.query_log_id,
        rating=request.rating,
        corrected_sql=request.corrected_sql,
        notes=request.notes,
    )
    db.add(feedback)

    # If corrected SQL provided, add to few-shot memory
    if request.corrected_sql:
        query_log_result = await db.execute(
            select(QueryLog).where(QueryLog.id == request.query_log_id)
        )
        query_log = query_log_result.scalar_one_or_none()
        if query_log:
            example = FewShotExample(
                nl_query=query_log.nl_query,
                bad_sql=query_log.final_sql,
                corrected_sql=request.corrected_sql,
                notes=request.notes,
                user_id=query_log.user_id,
                is_global=False,
            )
            db.add(example)

    await db.commit()
    await log.ainfo("feedback_recorded", query_log_id=str(request.query_log_id))
    return FeedbackResponse(id=feedback.id)


@router.get("/examples", response_model=list[FewShotExampleOut])
async def get_examples(
    user_id: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[FewShotExampleOut]:
    """Retrieve few-shot examples for a user."""
    examples: list[FewShotExample] = []

    # User-specific examples
    if user_id:
        user_stmt = (
            select(FewShotExample)
            .where(FewShotExample.user_id == user_id)
            .order_by(FewShotExample.created_at.desc())
            .limit(settings.querymind_few_shot_user_k)
        )
        result = await db.execute(user_stmt)
        examples.extend(result.scalars().all())

    # Global examples
    global_stmt = (
        select(FewShotExample)
        .where(FewShotExample.is_global.is_(True))
        .order_by(FewShotExample.created_at.desc())
        .limit(settings.querymind_few_shot_global_k)
    )
    result = await db.execute(global_stmt)
    examples.extend(result.scalars().all())

    return [FewShotExampleOut.model_validate(ex) for ex in examples]
