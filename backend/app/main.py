from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api.routes import router
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.models import Base, Connection
from app.db.session import async_session_factory, engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create tables on startup (dev convenience — use Alembic in production)."""
    setup_logging()
    key = settings.openai_api_key
    print(f"[STARTUP] OPENAI_API_KEY loaded: {'yes' if key else 'NO'} (length={len(key)}, starts_with={key[:8]}...)" if key else "[STARTUP] OPENAI_API_KEY is EMPTY")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed a default connection from TARGET_DATABASE_URL if none exists
    async with async_session_factory() as session:
        result = await session.execute(
            select(Connection).where(Connection.name == "default")
        )
        if not result.scalar_one_or_none():
            session.add(
                Connection(
                    name="default",
                    database_url=settings.target_database_url,
                )
            )
            await session.commit()

    yield
    await engine.dispose()


app = FastAPI(
    title="QueryMind",
    description="Natural-language-to-SQL with safety, validation, and self-correction",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
