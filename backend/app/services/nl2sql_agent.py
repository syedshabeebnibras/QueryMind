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
6. Return ALL relevant columns in the output, not just IDs. Include computed metrics,
   descriptive columns (department, name, title, etc.), and any columns that provide context.

SQL best practices you MUST follow for accurate results:

WINDOW FUNCTIONS:
- For comparing rows within the same table (e.g., consecutive events, repeated transactions,
  time-based patterns), ALWAYS use window functions (LAG, LEAD, ROW_NUMBER, RANK) with
  PARTITION BY and ORDER BY instead of self-joins.
- For "growth from previous row" or "change from prior value", ALWAYS use LAG() (looks backward),
  NOT LEAD() (looks forward). LAG(col) OVER (PARTITION BY id ORDER BY date) gives the PREVIOUS
  row's value. growth_pct = ((current - LAG(current)) / LAG(current)) * 100.
- For "consecutive days/periods" questions, use LAG() or ROW_NUMBER() with date arithmetic.
- For "within N minutes" or time-window comparisons, use LAG() to compare each row to its
  immediate predecessor.

HALF-SPLITTING PATTERN (use this exact CTE structure):
  CTE 1 (base): Compute ROW_NUMBER() and COUNT(*) OVER (PARTITION BY id) as total_records,
    plus LAG() for previous values. Keep ALL original columns.
  CTE 2 (growth_rows): Filter WHERE prev_value IS NOT NULL, compute growth_pct.
    Keep rn and total_records from the base CTE.
  CTE 3 (split): Assign half using the ORIGINAL row number (rn from base CTE):
    CASE WHEN rn <= FLOOR(total_records / 2.0) THEN 'first_half' ELSE 'second_half' END
    ALWAYS use FLOOR — this puts the extra row in the second half when count is odd.
    NEVER use CEIL for the first-half boundary.
  CTE 4 (aggregate): GROUP BY id, compute AVG for each half using:
    AVG(CASE WHEN half = 'first_half' THEN metric END) AS first_half_avg
    AVG(CASE WHEN half = 'second_half' THEN metric END) AS second_half_avg
  Final SELECT: JOIN with any additional filter CTEs, apply WHERE conditions.

LATEST ROW PATTERN:
- To get the latest/most recent row per group, use ROW_NUMBER() OVER (PARTITION BY id
  ORDER BY date DESC) AS latest_rn, then filter WHERE latest_rn = 1 in the next CTE.
  NEVER use correlated subqueries with MAX(date) — they are slower and error-prone.

RECORD COUNT FILTERING:
- When the question says "at least N records", ALWAYS enforce this with a separate CTE or
  in the final WHERE clause. Use COUNT(*) OVER or a dedicated count CTE.

COLUMN ALIAS RULE:
- CRITICAL PostgreSQL rule: You CANNOT reference a column alias from SELECT in WHERE or HAVING
  of the SAME query level. Wrap in a CTE/subquery and filter in the outer query.

GENERAL:
- Always CAST text/string columns to the appropriate type before arithmetic.
- Prefer CTEs (WITH ... AS) for multi-step logic — one computation per CTE.
- For finding the most common value (mode), use COUNT + ROW_NUMBER with ORDER BY count DESC.
- When counting duplicates, count only the later occurrence, not both sides.

"""


class NL2SQLGenerationError(Exception):
    """Raised when the LLM output is not a SQL statement."""


def build_few_shot_prompt(examples: list[FewShotExampleOut]) -> str:
    """Format few-shot examples for injection into the system prompt."""
    if not examples:
        return ""

    lines = [
        "Here are corrections from past queries. Learn from these mistakes "
        "and use the corrected SQL as the reference:\n"
    ]
    for ex in examples:
        lines.append(f"Question: {ex.nl_query}")
        if ex.bad_sql:
            lines.append(f"Wrong SQL: {ex.bad_sql}")
        lines.append(f"Correct SQL: {ex.corrected_sql}")
        if ex.notes:
            lines.append(f"Why it was wrong: {ex.notes}")
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
