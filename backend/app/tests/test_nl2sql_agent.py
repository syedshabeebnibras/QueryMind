"""Tests for NL->SQL output extraction and SQL-only guard."""

from app.services.nl2sql_agent import _extract_sql, _looks_like_sql_query


def test_extract_sql_strips_fence() -> None:
    raw = "```sql\nSELECT name FROM sample_employees LIMIT 5\n```"
    assert _extract_sql(raw) == "SELECT name FROM sample_employees LIMIT 5"


def test_looks_like_sql_accepts_select_and_with() -> None:
    assert _looks_like_sql_query("SELECT * FROM sample_employees LIMIT 1")
    assert _looks_like_sql_query("WITH t AS (SELECT 1) SELECT * FROM t")


def test_looks_like_sql_rejects_narrative_output() -> None:
    text = (
        "The sample_employees table does not contain manager_id, "
        "so I cannot build that comparison query."
    )
    assert not _looks_like_sql_query(text)
