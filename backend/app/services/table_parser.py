"""Table parser — converts raw table data (markdown, CSV, TSV) into SQL DDL + INSERT.

Accepts pasted table data in common formats and produces CREATE TABLE + INSERT statements.
"""

import csv
import io
import re
from datetime import datetime


class TableParseError(Exception):
    """Raised when table data cannot be parsed."""


def parse_table_to_sql(raw_data: str, table_name: str = "user_table") -> str:
    """Parse raw table data and return CREATE TABLE + INSERT INTO SQL.

    Supports:
    - Markdown tables (| col1 | col2 |)
    - CSV data
    - TSV data
    """
    raw_data = raw_data.strip()
    if not raw_data:
        raise TableParseError("No data provided.")

    # Detect format and parse
    if "|" in raw_data.split("\n")[0]:
        headers, rows = _parse_markdown_table(raw_data)
    elif "\t" in raw_data.split("\n")[0]:
        headers, rows = _parse_delimited(raw_data, delimiter="\t")
    else:
        headers, rows = _parse_delimited(raw_data, delimiter=",")

    if not headers:
        raise TableParseError("Could not detect column headers.")
    if not rows:
        raise TableParseError("No data rows found.")

    # Clean headers — make them valid SQL identifiers
    clean_headers = [_clean_column_name(h) for h in headers]

    # Infer column types from data
    col_types = [_infer_type(clean_headers[i], [row[i] for row in rows]) for i in range(len(clean_headers))]

    # Build SQL
    table_name = _clean_column_name(table_name)
    col_defs = ", ".join(f"{h} {t}" for h, t in zip(clean_headers, col_types))
    create_sql = f"CREATE TABLE {table_name} ({col_defs});"

    # Build INSERT statements
    insert_rows = []
    for row in rows:
        values = []
        for i, val in enumerate(row):
            values.append(_format_value(val, col_types[i]))
        insert_rows.append(f"({', '.join(values)})")

    # Batch inserts (max 100 per statement to avoid huge queries)
    insert_statements = []
    col_list = ", ".join(clean_headers)
    for batch_start in range(0, len(insert_rows), 100):
        batch = insert_rows[batch_start:batch_start + 100]
        insert_statements.append(
            f"INSERT INTO {table_name} ({col_list}) VALUES\n" + ",\n".join(batch) + ";"
        )

    return "\n\n".join([create_sql] + insert_statements)


def _parse_markdown_table(text: str) -> tuple[list[str], list[list[str]]]:
    """Parse a markdown-style table."""
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]

    # Find header row (first row with |)
    header_line = None
    data_start = 0
    for i, line in enumerate(lines):
        if "|" in line:
            header_line = line
            data_start = i + 1
            break

    if not header_line:
        raise TableParseError("No markdown table header found.")

    headers = [cell.strip() for cell in header_line.split("|") if cell.strip()]

    # Skip separator row (e.g., | --- | --- |)
    rows = []
    for line in lines[data_start:]:
        if not line or re.match(r"^[\|\s\-:]+$", line):
            continue
        cells = [cell.strip() for cell in line.split("|") if cell.strip()]
        if len(cells) == len(headers):
            rows.append(cells)

    return headers, rows


def _parse_delimited(text: str, delimiter: str) -> tuple[list[str], list[list[str]]]:
    """Parse CSV or TSV data."""
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    all_rows = list(reader)

    if len(all_rows) < 2:
        raise TableParseError("Need at least a header row and one data row.")

    headers = [h.strip() for h in all_rows[0]]
    rows = []
    for row in all_rows[1:]:
        stripped = [cell.strip() for cell in row]
        if len(stripped) == len(headers) and any(cell for cell in stripped):
            rows.append(stripped)

    return headers, rows


def _clean_column_name(name: str) -> str:
    """Convert a string to a valid SQL column name."""
    # Replace spaces and special chars with underscores
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", name.strip())
    # Remove leading/trailing underscores
    cleaned = cleaned.strip("_")
    # Ensure it starts with a letter
    if cleaned and not cleaned[0].isalpha():
        cleaned = "col_" + cleaned
    # Lowercase
    cleaned = cleaned.lower()
    return cleaned or "column"


def _infer_type(col_name: str, values: list[str]) -> str:
    """Infer PostgreSQL column type from sample values."""
    # Filter out empty/null values for type inference
    non_empty = [v for v in values if v and v.lower() not in ("null", "none", "n/a", "")]

    if not non_empty:
        return "TEXT"

    # Check if all values are integers
    if all(_is_integer(v) for v in non_empty):
        return "INTEGER"

    # Check if all values are floats/decimals
    if all(_is_float(v) for v in non_empty):
        return "NUMERIC"

    # Check if all values are timestamps (with time component)
    if all(_is_timestamp(v) for v in non_empty):
        return "TIMESTAMP"

    # Check if all values are dates (date only, no time)
    if all(_is_date(v) for v in non_empty):
        return "DATE"

    # Check if all values are booleans
    if all(v.lower() in ("true", "false", "yes", "no", "0", "1") for v in non_empty):
        return "BOOLEAN"

    return "TEXT"


def _is_integer(value: str) -> bool:
    try:
        int(value.replace(",", ""))
        return True
    except ValueError:
        return False


def _is_float(value: str) -> bool:
    try:
        float(value.replace(",", ""))
        return True
    except ValueError:
        return False


def _is_timestamp(value: str) -> bool:
    """Check if value is a datetime with time component."""
    timestamp_patterns = [
        "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%m/%d/%Y %H:%M",
    ]
    for pattern in timestamp_patterns:
        try:
            datetime.strptime(value, pattern)
            return True
        except ValueError:
            continue
    return False


def _is_date(value: str) -> bool:
    """Check if value is a date (no time component)."""
    date_patterns = [
        "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y",
    ]
    for pattern in date_patterns:
        try:
            datetime.strptime(value, pattern)
            return True
        except ValueError:
            continue
    return False


def _format_value(value: str, col_type: str) -> str:
    """Format a value for SQL INSERT based on inferred type."""
    if not value or value.lower() in ("null", "none", "n/a"):
        return "NULL"

    if col_type == "INTEGER":
        return str(int(value.replace(",", "")))

    if col_type == "NUMERIC":
        return str(float(value.replace(",", "")))

    if col_type == "BOOLEAN":
        return "TRUE" if value.lower() in ("true", "yes", "1") else "FALSE"

    # TEXT and DATE — quote with escaped single quotes
    escaped = value.replace("'", "''")
    return f"'{escaped}'"
