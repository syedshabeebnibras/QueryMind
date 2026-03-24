"""Schema setup service — executes user-provided DDL to provision tables.

Only allows CREATE TABLE, INSERT INTO, and DROP TABLE statements.
Blocks all other DDL/DML for safety.
"""

import sqlglot
from sqlglot import exp

import psycopg2

from app.core.config import settings
from app.core.logging import log


class SchemaSetupError(Exception):
    """Raised when schema setup DDL is invalid or blocked."""


# Statement types allowed during schema setup
_ALLOWED_TYPES = (exp.Create, exp.Insert, exp.Drop)


def validate_setup_sql(sql: str) -> list[str]:
    """Parse and validate DDL for schema setup.

    Returns a list of individual safe SQL statements.
    Raises SchemaSetupError if any statement is not allowed.
    """
    try:
        statements = sqlglot.parse(sql, read="postgres")
    except sqlglot.errors.ParseError as e:
        raise SchemaSetupError(f"SQL parse error: {e}") from e

    if not statements:
        raise SchemaSetupError("No SQL statements found.")

    validated: list[str] = []
    for stmt in statements:
        if stmt is None:
            continue

        # Allow CREATE TABLE / CREATE INDEX
        if isinstance(stmt, exp.Create):
            kind = stmt.args.get("kind")
            if kind and kind.upper() not in ("TABLE", "INDEX"):
                raise SchemaSetupError(
                    f"CREATE {kind} is not allowed. Only CREATE TABLE and CREATE INDEX are permitted."
                )
            # Auto-prepend DROP TABLE IF EXISTS for CREATE TABLE
            if kind and kind.upper() == "TABLE":
                table_expr = stmt.find(exp.Table)
                if table_expr:
                    table_name = table_expr.sql(dialect="postgres")
                    validated.append(f"DROP TABLE IF EXISTS {table_name} CASCADE")
            validated.append(stmt.sql(dialect="postgres"))
            continue

        # Allow INSERT
        if isinstance(stmt, exp.Insert):
            validated.append(stmt.sql(dialect="postgres"))
            continue

        # Allow DROP TABLE only
        if isinstance(stmt, exp.Drop):
            kind = stmt.args.get("kind")
            if kind and kind.upper() != "TABLE":
                raise SchemaSetupError(
                    f"DROP {kind} is not allowed. Only DROP TABLE is permitted."
                )
            validated.append(stmt.sql(dialect="postgres"))
            continue

        # Block everything else
        raise SchemaSetupError(
            f"Statement type '{type(stmt).__name__}' is not allowed. "
            "Only CREATE TABLE, INSERT INTO, and DROP TABLE are permitted."
        )

    if not validated:
        raise SchemaSetupError("No valid statements found.")

    return validated


def execute_setup_sql(
    sql: str, target_database_url: str | None = None
) -> dict:
    """Validate and execute schema setup DDL against the target database.

    Returns a summary of executed statements.
    """
    statements = validate_setup_sql(sql)

    db_url = target_database_url or settings.target_database_url
    # Use the main DB URL (not readonly) for schema setup — need write access
    # Replace readonly connection with the main querymind user
    setup_url = _get_write_url(db_url)

    conn = psycopg2.connect(setup_url)
    executed = []
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute(
                f"SET LOCAL statement_timeout = '{settings.querymind_statement_timeout}'"
            )
            for stmt_sql in statements:
                cur.execute(stmt_sql)
                executed.append(stmt_sql)
                log.info("schema_setup_executed", sql=stmt_sql[:200])
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise SchemaSetupError(f"Execution failed after {len(executed)} statements: {e}") from e
    finally:
        conn.close()

    # Invalidate schema cache so next query picks up new tables
    from app.services.schema_context import _schema_cache
    _schema_cache.clear()

    return {
        "statements_executed": len(executed),
        "statements": [s[:200] for s in executed],
    }


def _get_write_url(url: str) -> str:
    """Derive a write-capable URL from the target URL.

    If the URL uses the readonly role, swap to the main querymind role.
    Otherwise return as-is (user provided a write-capable URL).
    """
    if "querymind_readonly" in url:
        return url.replace(
            "querymind_readonly:readonly_dev",
            "querymind:querymind_dev",
        )
    return url
