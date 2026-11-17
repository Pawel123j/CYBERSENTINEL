"""FastAPI application factory."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from cybersentinel_backend import __version__
from cybersentinel_backend.api.health import router as health_router
from cybersentinel_backend.config import Settings, get_settings
from cybersentinel_backend.database import create_database_engine

EngineFactory = Callable[[Settings], AsyncEngine]


def create_app(
    settings: Settings | None = None,
    engine_factory: EngineFactory | None = None,
) -> FastAPI:
    """Create an independently configurable CyberSentinel API instance."""

    selected_engine_factory = engine_factory or create_database_engine

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        runtime_settings = settings or get_settings()
        engine = selected_engine_factory(runtime_settings)
        application.state.settings = runtime_settings
        application.state.database_engine = engine

        try:
            yield
        finally:
            await engine.dispose()

    application = FastAPI(
        title="CyberSentinel API",
        version=__version__,
        lifespan=lifespan,
    )
    application.include_router(health_router, prefix="/api")
    return application
