"""SQL safety enforcement using sqlglot AST parsing.

Rules:
1. Only SELECT statements allowed (with optional WITH/CTE prefix).
2. Single statement only — no multi-statement batches.
3. Block dangerous functions: pg_read_file, pg_read_binary_file, lo_*, COPY, etc.
4. Enforce LIMIT (service-imposed cap) unless the query is a simple aggregate.
"""

import sqlglot
from sqlglot import exp

from app.core.config import settings
from app.core.logging import log

# Statements we allow
_ALLOWED_STATEMENT_TYPES = {exp.Select}

# Functions that are explicitly blocked
_BLOCKED_FUNCTIONS = {
    "pg_read_file",
    "pg_read_binary_file",
    "pg_ls_dir",
    "pg_stat_file",
    "lo_import",
    "lo_export",
    "lo_get",
    "pg_sleep",
    "dblink",
    "dblink_exec",
    "copy",
}


class SQLSafetyError(Exception):
    """Raised when a SQL statement violates safety policies."""


def check_sql_safety(sql: str) -> str:
    """Validate and normalize a SQL string. Returns the normalized SQL or raises SQLSafetyError."""

    # Parse with sqlglot
    try:
        statements = sqlglot.parse(sql, dialect="postgres")
    except sqlglot.errors.ParseError as e:
        raise SQLSafetyError(f"SQL parse error: {e}") from e

    # Must be exactly one statement
    statements = [s for s in statements if s is not None]
    if len(statements) == 0:
        raise SQLSafetyError("Empty SQL statement")
    if len(statements) > 1:
        raise SQLSafetyError("Multiple statements not allowed — submit one query at a time")

    stmt = statements[0]

    # Must be a SELECT (or WITH ... SELECT which sqlglot parses as Select)
    if type(stmt) not in _ALLOWED_STATEMENT_TYPES:
        raise SQLSafetyError(
            f"Only SELECT queries are allowed. Got: {type(stmt).__name__}"
        )

    # Walk AST for blocked patterns
    for node in stmt.walk():
        # Block subquery DML (INSERT/UPDATE/DELETE/DROP/ALTER/CREATE inside subqueries)
        if isinstance(
            node,
            (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create, exp.Merge),
        ):
            raise SQLSafetyError(f"Forbidden statement type in query: {type(node).__name__}")

        # Block dangerous functions
        if isinstance(node, exp.Anonymous) or isinstance(node, exp.Func):
            func_name = ""
            if isinstance(node, exp.Anonymous):
                func_name = node.name.lower()
            elif hasattr(node, "sql_name"):
                func_name = node.sql_name().lower()

            if func_name in _BLOCKED_FUNCTIONS:
                raise SQLSafetyError(f"Blocked function: {func_name}")

        # Block INTO clause (SELECT ... INTO)
        if isinstance(node, exp.Into):
            raise SQLSafetyError("SELECT ... INTO is not allowed")

    # Enforce LIMIT unless it's a simple aggregate
    if not _has_limit(stmt) and not _is_simple_aggregate(stmt):
        log.info("enforcing_limit", max_rows=settings.querymind_max_rows)
        stmt = stmt.limit(settings.querymind_max_rows)

    return stmt.sql(dialect="postgres")


def _has_limit(stmt: exp.Expression) -> bool:
    """Check if the outermost SELECT has a LIMIT clause."""
    limit = stmt.find(exp.Limit)
    return limit is not None


def _is_simple_aggregate(stmt: exp.Expression) -> bool:
    """Check if the query is a simple aggregate (COUNT/SUM/AVG/etc.) with no GROUP BY
    that will return few rows."""
    # Has GROUP BY → could return many rows
    if stmt.find(exp.Group):
        return False

    # Check if all SELECT expressions are aggregate functions
    select_exprs = list(stmt.find_all(exp.Select))
    if not select_exprs:
        return False

    outermost = select_exprs[0]
    columns = outermost.expressions
    if not columns:
        return False

    agg_types = (exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max)
    return all(
        isinstance(col, agg_types) or (isinstance(col, exp.Alias) and isinstance(col.this, agg_types))
        for col in columns
    )
