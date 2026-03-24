"""EXPLAIN gate — runs EXPLAIN (FORMAT JSON) to check cost/row estimates before execution.

Blocks queries that exceed configured thresholds for total cost or estimated rows.
"""

from typing import Any

import psycopg2

from app.core.config import settings
from app.core.logging import log


class ExplainGateError(Exception):
    """Raised when a query exceeds EXPLAIN thresholds."""


def run_explain(sql: str, target_database_url: str | None = None) -> dict[str, Any]:
    """Run EXPLAIN (FORMAT JSON) on the target database and return plan summary.

    Uses a synchronous connection (psycopg2) since this runs against the target DB
    with the read-only role and statement_timeout.
    """
    explain_query = f"EXPLAIN (FORMAT JSON) {sql}"

    db_url = target_database_url or settings.target_database_url
    conn = psycopg2.connect(db_url)
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            # Safety: set statement timeout
            cur.execute(
                f"SET LOCAL statement_timeout = '{settings.querymind_statement_timeout}'"
            )
            cur.execute(explain_query)
            result = cur.fetchone()
            conn.rollback()  # Don't commit anything
    finally:
        conn.close()

    if not result or not result[0]:
        raise ExplainGateError("EXPLAIN returned no result")

    plan = result[0][0]  # EXPLAIN JSON returns [{Plan: {...}}]
    return _extract_summary(plan)


def check_explain_thresholds(summary: dict[str, Any]) -> None:
    """Raise ExplainGateError if the plan exceeds configured thresholds."""
    total_cost = summary.get("total_cost", 0)
    estimated_rows = summary.get("estimated_rows", 0)

    if total_cost > settings.querymind_max_explain_cost:
        raise ExplainGateError(
            f"Query too expensive: estimated cost {total_cost:.0f} "
            f"exceeds threshold {settings.querymind_max_explain_cost:.0f}. "
            "Please refine your query to be more specific."
        )

    if estimated_rows > settings.querymind_max_explain_rows:
        raise ExplainGateError(
            f"Query returns too many rows: estimated {estimated_rows:,} "
            f"exceeds threshold {settings.querymind_max_explain_rows:,}. "
            "Please add filters or aggregations."
        )

    log.info(
        "explain_gate_passed",
        total_cost=total_cost,
        estimated_rows=estimated_rows,
    )


def _extract_summary(plan: dict[str, Any]) -> dict[str, Any]:
    """Extract useful summary from EXPLAIN JSON output."""
    root_plan = plan.get("Plan", {})

    total_cost = root_plan.get("Total Cost", 0)
    estimated_rows = root_plan.get("Plan Rows", 0)

    # Count plan nodes
    node_count = 0
    stack = [root_plan]
    while stack:
        node = stack.pop()
        node_count += 1
        stack.extend(node.get("Plans", []))

    return {
        "total_cost": total_cost,
        "estimated_rows": estimated_rows,
        "plan_nodes": node_count,
        "node_type": root_plan.get("Node Type", "Unknown"),
    }
