import ssl
from collections.abc import AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


def _prepare_asyncpg_url(url: str) -> tuple[str, dict]:
    """Strip query params unsupported by asyncpg and return (clean_url, connect_args)."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    connect_args: dict = {}

    # asyncpg uses 'ssl' kwarg instead of 'sslmode' query param
    if "sslmode" in params:
        mode = params.pop("sslmode")[0]
        if mode in ("require", "prefer", "verify-ca", "verify-full"):
            connect_args["ssl"] = ssl.create_default_context()

    # channel_binding is not supported by asyncpg as a query param
    params.pop("channel_binding", None)

    clean_query = urlencode({k: v[0] for k, v in params.items()})
    clean_url = urlunparse(parsed._replace(query=clean_query))
    return clean_url, connect_args


_db_url, _connect_args = _prepare_asyncpg_url(settings.database_url)

engine = create_async_engine(
    _db_url,
    echo=False,
    pool_size=5,
    max_overflow=10,
    connect_args=_connect_args,
)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session for dependency injection."""
    async with async_session_factory() as session:
        yield session
