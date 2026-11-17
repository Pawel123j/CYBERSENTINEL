"""Asynchronous database engine construction and injection."""

from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from cybersentinel_backend.config import Settings

DATABASE_OPERATION_TIMEOUT_SECONDS = 3.0


def create_database_engine(settings: Settings) -> AsyncEngine:
    """Create the shared SQLAlchemy engine for the application process."""

    return create_async_engine(
        settings.database_url,
        connect_args={
            "command_timeout": DATABASE_OPERATION_TIMEOUT_SECONDS,
            "timeout": DATABASE_OPERATION_TIMEOUT_SECONDS,
        },
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_timeout=DATABASE_OPERATION_TIMEOUT_SECONDS,
    )


def get_database_engine(request: Request) -> AsyncEngine:
    """Provide the engine initialized by the application lifespan."""

    try:
        return cast(AsyncEngine, request.app.state.database_engine)
    except AttributeError as error:
        raise RuntimeError("Database engine is not initialized") from error
