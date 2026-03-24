"""Schema introspection service — provides live schema context for LLM prompts.

Connects to a target database, reflects tables/columns/types/FKs, and formats
them into a compact text blob. Supports optional DDL overrides and TTL caching.
"""

import hashlib
import time
from typing import Any

import psycopg2

from app.core.config import settings
from app.core.logging import log

# In-memory cache: key → (schema_text, timestamp)
_schema_cache: dict[str, tuple[str, float]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes

_MAX_SCHEMA_CHARS = 12_000  # Cap to avoid blowing up the prompt


def get_schema_context(
    target_database_url: str,
    schema_ddl: str | None = None,
    connection_id: str | None = None,
) -> str:
    """Return a prompt-friendly schema description for the target database.

    If schema_ddl is provided, it takes priority over introspection.
    Results are cached by connection_id + database fingerprint with a TTL.
    """
    if schema_ddl:
        log.info("schema_context_from_ddl", length=len(schema_ddl))
        return _truncate(schema_ddl)

    cache_key = _make_cache_key(target_database_url, connection_id)
    cached = _schema_cache.get(cache_key)
    if cached:
        text, ts = cached
        if time.monotonic() - ts < _CACHE_TTL_SECONDS:
            log.info("schema_context_cache_hit", key=cache_key)
            return text

    schema_text = _introspect(target_database_url)
    _schema_cache[cache_key] = (schema_text, time.monotonic())
    log.info("schema_context_introspected", length=len(schema_text))
    return schema_text


def _make_cache_key(url: str, connection_id: str | None) -> str:
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]
    return f"{connection_id or 'default'}:{url_hash}"


def _introspect(database_url: str) -> str:
    """Reflect schema via information_schema and format for LLM consumption."""
    conn = psycopg2.connect(database_url)
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute(
                f"SET LOCAL statement_timeout = '{settings.querymind_statement_timeout}'"
            )

            # Get tables
            cur.execute("""
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                  AND table_type = 'BASE TABLE'
                ORDER BY table_schema, table_name
            """)
            tables = cur.fetchall()

            # Get columns
            cur.execute("""
                SELECT table_schema, table_name, column_name, data_type,
                       is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY table_schema, table_name, ordinal_position
            """)
            columns = cur.fetchall()

            # Get foreign keys
            cur.execute("""
                SELECT
                    tc.table_schema, tc.table_name, kcu.column_name,
                    ccu.table_schema AS ref_schema,
                    ccu.table_name AS ref_table,
                    ccu.column_name AS ref_column
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage ccu
                    ON tc.constraint_name = ccu.constraint_name
                    AND tc.table_schema = ccu.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                ORDER BY tc.table_schema, tc.table_name
            """)
            fks = cur.fetchall()

            conn.rollback()
    finally:
        conn.close()

    return _truncate(_format_schema(tables, columns, fks))


def _format_schema(
    tables: list[tuple],
    columns: list[tuple],
    fks: list[tuple],
) -> str:
    """Format introspection results into compact DDL-like text."""
    # Group columns by (schema, table)
    col_map: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for schema, table, col_name, data_type, nullable, default in columns:
        key = (schema, table)
        col_map.setdefault(key, []).append({
            "name": col_name,
            "type": data_type,
            "nullable": nullable == "YES",
            "default": default,
        })

    # Group FKs by (schema, table)
    fk_map: dict[tuple[str, str], list[str]] = {}
    for schema, table, col, ref_schema, ref_table, ref_col in fks:
        key = (schema, table)
        fk_map.setdefault(key, []).append(
            f"  FK: {col} -> {ref_schema}.{ref_table}({ref_col})"
        )

    lines = ["-- Database Schema\n"]
    for schema, table in tables:
        qualified = f"{schema}.{table}" if schema != "public" else table
        lines.append(f"TABLE {qualified} (")
        for col in col_map.get((schema, table), []):
            null_str = "" if col["nullable"] else " NOT NULL"
            lines.append(f"  {col['name']} {col['type']}{null_str},")
        for fk_line in fk_map.get((schema, table), []):
            lines.append(f"{fk_line},")
        lines.append(")\n")

    return "\n".join(lines)


def _truncate(text: str) -> str:
    if len(text) <= _MAX_SCHEMA_CHARS:
        return text
    return text[:_MAX_SCHEMA_CHARS] + "\n-- [schema truncated due to size]\n"
