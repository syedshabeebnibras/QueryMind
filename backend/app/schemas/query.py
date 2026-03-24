import datetime
import uuid

from pydantic import BaseModel, Field


class ConnectionCreate(BaseModel):
    """Create a new target database connection."""

    name: str = Field(..., min_length=1, max_length=255)
    database_url: str = Field(..., min_length=1)
    owner_user_id: str | None = Field(None, max_length=255)


class ConnectionOut(BaseModel):
    id: uuid.UUID
    name: str
    owner_user_id: str | None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class QueryRequest(BaseModel):
    """Request to translate NL to SQL and execute."""

    nl_query: str = Field(..., min_length=1, max_length=2000, description="Natural language query")
    user_id: str | None = Field(None, max_length=255)
    connection_id: uuid.UUID | None = Field(None, description="Target connection ID")
    schema_ddl: str | None = Field(None, max_length=50000, description="Optional DDL override")


class ExplainSummary(BaseModel):
    total_cost: float
    estimated_rows: int
    plan_nodes: int


class ValidationSummary(BaseModel):
    success: bool
    expectations_evaluated: int
    expectations_passed: int
    details: list[dict] = []


class QueryResponse(BaseModel):
    query_id: uuid.UUID
    nl_query: str
    final_sql: str | None
    columns: list[str] = []
    rows: list[list] = []
    row_count: int = 0
    runtime_ms: float = 0
    explain_summary: ExplainSummary | None = None
    validation_summary: ValidationSummary | None = None
    status: str
    error: str | None = None
    attempted_sqls: list[str] = []


class QueryHistoryItem(BaseModel):
    id: uuid.UUID
    nl_query: str
    final_sql: str | None
    status: str
    row_count: int | None
    runtime_ms: float | None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class QueryHistoryResponse(BaseModel):
    items: list[QueryHistoryItem]
    total: int
    page: int
    page_size: int


class FeedbackRequest(BaseModel):
    query_log_id: uuid.UUID
    rating: int = Field(..., ge=1, le=5)
    corrected_sql: str | None = None
    notes: str | None = None


class FeedbackResponse(BaseModel):
    id: uuid.UUID
    message: str = "Feedback recorded"


class FewShotExampleOut(BaseModel):
    nl_query: str
    bad_sql: str | None = None
    corrected_sql: str
    notes: str | None

    model_config = {"from_attributes": True}


class TableDataRequest(BaseModel):
    """Request to import raw table data (markdown, CSV, TSV) into the database."""

    table_data: str = Field(..., min_length=1, max_length=100_000_000, description="Raw table data (markdown, CSV, or TSV)")
    table_name: str = Field("user_table", min_length=1, max_length=100, description="Name for the table")
    connection_id: uuid.UUID | None = Field(None, description="Target connection ID")


class TableDataResponse(BaseModel):
    status: str
    table_name: str = ""
    columns: list[str] = []
    row_count: int = 0
    generated_sql: str = ""
    error: str | None = None


class SchemaSetupRequest(BaseModel):
    """Request to execute DDL to set up tables in the target database."""

    ddl: str = Field(..., min_length=1, max_length=100000, description="SQL DDL (CREATE TABLE, INSERT, DROP TABLE)")
    connection_id: uuid.UUID | None = Field(None, description="Target connection ID")


class SchemaSetupResponse(BaseModel):
    status: str
    statements_executed: int = 0
    statements: list[str] = []
    error: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    database: str = "ok"
