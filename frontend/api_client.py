"""HTTP client for communicating with the QueryMind FastAPI backend."""

import os
from typing import Any

import httpx

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
TIMEOUT = 120.0  # NL→SQL can be slow


async def run_query(
    nl_query: str,
    user_id: str | None = None,
    connection_id: str | None = None,
    schema_ddl: str | None = None,
) -> dict[str, Any]:
    """POST /query — run the NL→SQL pipeline."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        payload: dict[str, Any] = {"nl_query": nl_query}
        if user_id:
            payload["user_id"] = user_id
        if connection_id:
            payload["connection_id"] = connection_id
        if schema_ddl:
            payload["schema_ddl"] = schema_ddl
        resp = await client.post(f"{BACKEND_URL}/query", json=payload)
        resp.raise_for_status()
        return resp.json()


async def get_connections() -> list[dict[str, Any]]:
    """GET /connections — list available target connections."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{BACKEND_URL}/connections")
        resp.raise_for_status()
        return resp.json()


async def create_connection(
    name: str, database_url: str, owner_user_id: str | None = None
) -> dict[str, Any]:
    """POST /connections — add a new target connection."""
    async with httpx.AsyncClient(timeout=30) as client:
        payload: dict[str, Any] = {"name": name, "database_url": database_url}
        if owner_user_id:
            payload["owner_user_id"] = owner_user_id
        resp = await client.post(f"{BACKEND_URL}/connections", json=payload)
        resp.raise_for_status()
        return resp.json()


async def delete_connection(connection_id: str) -> None:
    """DELETE /connections/{id} — remove a connection."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.delete(f"{BACKEND_URL}/connections/{connection_id}")
        resp.raise_for_status()


async def import_table(
    table_data: str, table_name: str = "user_table", connection_id: str | None = None
) -> dict[str, Any]:
    """POST /table/import — import raw table data into the database."""
    async with httpx.AsyncClient(timeout=300) as client:
        payload: dict[str, Any] = {"table_data": table_data, "table_name": table_name}
        if connection_id:
            payload["connection_id"] = connection_id
        resp = await client.post(f"{BACKEND_URL}/table/import", json=payload)
        resp.raise_for_status()
        return resp.json()


async def setup_schema(
    ddl: str, connection_id: str | None = None
) -> dict[str, Any]:
    """POST /schema/setup — execute DDL to create tables and insert data."""
    async with httpx.AsyncClient(timeout=60) as client:
        payload: dict[str, Any] = {"ddl": ddl}
        if connection_id:
            payload["connection_id"] = connection_id
        resp = await client.post(f"{BACKEND_URL}/schema/setup", json=payload)
        resp.raise_for_status()
        return resp.json()


async def get_history(
    page: int = 1, page_size: int = 20, status: str | None = None, user_id: str | None = None
) -> dict[str, Any]:
    """GET /history — paginated query history."""
    async with httpx.AsyncClient(timeout=30) as client:
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if status:
            params["status"] = status
        if user_id:
            params["user_id"] = user_id
        resp = await client.get(f"{BACKEND_URL}/history", params=params)
        resp.raise_for_status()
        return resp.json()


async def submit_feedback(
    query_log_id: str,
    rating: int,
    corrected_sql: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """POST /feedback — submit user feedback."""
    async with httpx.AsyncClient(timeout=30) as client:
        payload: dict[str, Any] = {
            "query_log_id": query_log_id,
            "rating": rating,
        }
        if corrected_sql:
            payload["corrected_sql"] = corrected_sql
        if notes:
            payload["notes"] = notes
        resp = await client.post(f"{BACKEND_URL}/feedback", json=payload)
        resp.raise_for_status()
        return resp.json()


async def health_check() -> dict[str, Any]:
    """GET /health."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{BACKEND_URL}/health")
        resp.raise_for_status()
        return resp.json()
