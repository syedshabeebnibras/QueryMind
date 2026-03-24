import datetime
import uuid

from sqlalchemy import Boolean, DateTime, Float, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class QueryLog(Base):
    """Full audit trail for every query attempt."""

    __tablename__ = "query_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    nl_query: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(255))
    connection_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    attempted_sqls: Mapped[list] = mapped_column(JSONB, default=list)
    final_sql: Mapped[str | None] = mapped_column(Text)
    explain_summary: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending, success, error, blocked
    error: Mapped[str | None] = mapped_column(Text)
    row_count: Mapped[int | None] = mapped_column(Integer)
    runtime_ms: Mapped[float | None] = mapped_column(Float)
    validation_result: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Feedback(Base):
    """User feedback on query results."""

    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    query_log_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1=thumbs down, 5=thumbs up
    corrected_sql: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class FewShotExample(Base):
    """Adaptive few-shot memory for prompt engineering."""

    __tablename__ = "few_shot_examples"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    nl_query: Mapped[str] = mapped_column(Text, nullable=False)
    bad_sql: Mapped[str | None] = mapped_column(Text)
    corrected_sql: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[str | None] = mapped_column(String(255))
    is_global: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Connection(Base):
    """Named target database connections."""

    __tablename__ = "connections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    database_url: Mapped[str] = mapped_column(Text, nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class QueryMetrics(Base):
    """Per-query performance metrics."""

    __tablename__ = "query_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    query_log_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    explain_cost: Mapped[float | None] = mapped_column(Numeric(12, 2))
    explain_rows: Mapped[int | None] = mapped_column(Integer)
    execution_ms: Mapped[float | None] = mapped_column(Float)
    row_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
