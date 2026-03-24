"""LangChain-based NL→SQL generation with few-shot memory injection.

Uses a direct ChatOpenAI call with schema context instead of a multi-step agent
for faster, more predictable SQL generation.
"""

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.config import settings
from app.core.logging import log
from app.schemas.query import FewShotExampleOut

_SYSTEM_PREFIX = """You are a SQL expert. Given a natural language question, generate a single
PostgreSQL SELECT query that answers it. Follow these rules strictly:

1. Only generate SELECT statements (WITH...SELECT is OK — prefer CTEs for clarity).
2. Never use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, or any DDL/DML.
3. Always include a LIMIT clause unless the query is a simple aggregate (COUNT, SUM, AVG, etc.).
4. Use proper PostgreSQL syntax.
5. Return ONLY the SQL query, no explanation or markdown.

SQL best practices you MUST follow for accurate results:

- For comparing rows within the same table (e.g., consecutive events, repeated transactions,
  time-based patterns), ALWAYS use window functions (LAG, LEAD, ROW_NUMBER, RANK) with
  PARTITION BY and ORDER BY instead of self-joins. Self-joins double-count pairs and produce
  wrong results.
- For "consecutive days/periods" questions, use LAG() or ROW_NUMBER() with date arithmetic
  to detect gaps, not self-joins or cross joins.
- For "within N minutes" or time-window comparisons, use LAG() OVER (PARTITION BY ... ORDER BY timestamp)
  to compare each row only to its immediate predecessor, avoiding double-counting.
- When counting duplicates or repeated events, count only the later occurrence in each pair,
  not both sides.
- Always CAST text/string columns to the appropriate type (TIMESTAMP, DATE, NUMERIC) before
  doing arithmetic or comparisons on them.
- Prefer CTEs (WITH ... AS) for multi-step logic to keep queries readable and correct.
- For splitting data into halves, use ROW_NUMBER() and CEIL/FLOOR with COUNT().
- For finding the most common value (mode), use COUNT + RANK or ROW_NUMBER with ORDER BY count DESC.

"""


class NL2SQLGenerationError(Exception):
    """Raised when the LLM output is not a SQL statement."""


def build_few_shot_prompt(examples: list[FewShotExampleOut]) -> str:
    """Format few-shot examples for injection into the system prompt."""
    if not examples:
        return ""

    lines = ["Here are some example question→SQL pairs for reference:\n"]
    for ex in examples:
        lines.append(f"Question: {ex.nl_query}")
        lines.append(f"SQL: {ex.corrected_sql}")
        if ex.notes:
            lines.append(f"Note: {ex.notes}")
        lines.append("")
    return "\n".join(lines)


async def generate_sql(
    nl_query: str,
    few_shot_examples: list[FewShotExampleOut] | None = None,
    target_database_url: str | None = None,
    schema_context: str | None = None,
) -> str:
    """Generate SQL from natural language using a direct LLM call."""
    few_shot_text = build_few_shot_prompt(few_shot_examples or [])

    schema_section = ""
    if schema_context:
        schema_section = (
            "The database has the following schema:\n"
            f"{schema_context}\n\n"
        )

    system_prompt = _SYSTEM_PREFIX + schema_section + few_shot_text

    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        api_key=settings.openai_api_key,
        request_timeout=60,
    )

    await log.ainfo("generating_sql", nl_query=nl_query)

    response = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=nl_query),
    ])

    raw_output = response.content

    # Extract SQL from response — LLM may wrap it in markdown
    sql = _extract_sql(raw_output)
    if not _looks_like_sql_query(sql):
        raise NL2SQLGenerationError(
            "Model did not return a SQL query. The requested relationship may not exist "
            "in the current schema."
        )
    await log.ainfo("sql_generated", sql=sql)
    return sql


def _extract_sql(text: str) -> str:
    """Extract SQL from agent output, stripping markdown fences if present."""
    text = text.strip()
    if text.startswith("```sql"):
        text = text[6:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _looks_like_sql_query(text: str) -> bool:
    """Heuristic guard to reject narrative model output before SQL safety parsing."""
    stripped = text.strip().lower()
    return stripped.startswith("select ") or stripped.startswith("with ")
