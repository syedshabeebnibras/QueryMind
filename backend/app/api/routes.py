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
from app.services.table_parser import TableParseError, parse_table_to_sql

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

    Parses the data, infers types, creates the table, and inserts all rows.
    """
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
        # Parse raw data into SQL
        generated_sql = parse_table_to_sql(request.table_data, request.table_name)

        # Execute it via the schema setup service
        summary = execute_setup_sql(generated_sql, target_database_url=target_url)

        # Extract column info from the generated SQL for the response
        lines = generated_sql.split("\n")
        create_line = lines[0] if lines else ""
        # Count INSERT rows
        row_count = generated_sql.count("(") - 1  # subtract CREATE TABLE parens
        # Rough column extraction
        import re
        col_matches = re.findall(r"INSERT INTO \w+ \((.+?)\) VALUES", generated_sql)
        columns = [c.strip() for c in col_matches[0].split(",")] if col_matches else []

        await log.ainfo(
            "table_imported",
            table_name=request.table_name,
            columns=len(columns),
            rows=row_count,
        )
        return TableDataResponse(
            status="success",
            table_name=request.table_name,
            columns=columns,
            row_count=row_count,
            generated_sql=generated_sql,
        )
    except TableParseError as e:
        return TableDataResponse(status="error", error=f"Parse error: {e}")
    except SchemaSetupError as e:
        return TableDataResponse(status="error", error=f"Setup error: {e}")


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
