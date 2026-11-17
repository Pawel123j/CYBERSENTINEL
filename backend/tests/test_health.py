"""Health endpoint tests."""

import asyncio
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from cybersentinel_backend.api import health
from cybersentinel_backend.config import Settings
from cybersentinel_backend.database import get_database_engine
from cybersentinel_backend.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(
        postgres_host="database",
        postgres_port=5432,
        postgres_db="cybersentinel_test",
        postgres_user="cybersentinel_test",
        postgres_password="test-password",
    )


@pytest.fixture
def lifecycle_engine() -> MagicMock:
    return MagicMock(spec=AsyncEngine)


@pytest.fixture
def app(settings: Settings, lifecycle_engine: MagicMock) -> FastAPI:
    return create_app(
        settings=settings,
        engine_factory=lambda _: cast(AsyncEngine, lifecycle_engine),
    )


def create_probe_engine(error: Exception | None = None) -> tuple[AsyncEngine, AsyncMock]:
    connection = MagicMock(spec=AsyncConnection)
    execute = AsyncMock(side_effect=error)
    connection.execute = execute

    connection_context = MagicMock()
    connection_context.__aenter__ = AsyncMock(return_value=connection)
    connection_context.__aexit__ = AsyncMock(return_value=False)

    engine = MagicMock(spec=AsyncEngine)
    engine.connect.return_value = connection_context
    return cast(AsyncEngine, engine), execute


def override_engine(app: FastAPI, engine: AsyncEngine) -> None:
    def provide_engine() -> AsyncEngine:
        return engine

    app.dependency_overrides[get_database_engine] = provide_engine


def test_liveness_reports_version(app: FastAPI) -> None:
    with TestClient(app) as client:
        response = client.get("/api/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_readiness_executes_select_one(app: FastAPI) -> None:
    probe_engine, execute = create_probe_engine()
    override_engine(app, probe_engine)

    with TestClient(app) as client:
        response = client.get("/api/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "version": "0.1.0"}
    execute.assert_awaited_once()
    statement = execute.await_args.args[0]
    assert str(statement) == "SELECT 1"


def test_readiness_failure_is_sanitized(app: FastAPI) -> None:
    private_error = "database-secret.internal:5432 rejected credentials"
    probe_engine, execute = create_probe_engine(RuntimeError(private_error))
    override_engine(app, probe_engine)

    with TestClient(app) as client:
        response = client.get("/api/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Service is not ready"}
    assert private_error not in response.text
    assert response.headers["retry-after"] == "5"
    execute.assert_awaited_once()


def test_readiness_timeout_is_bounded_and_sanitized(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def delayed_query(*_: object) -> None:
        await asyncio.sleep(1)

    probe_engine, execute = create_probe_engine()
    execute.side_effect = delayed_query
    override_engine(app, probe_engine)
    monkeypatch.setattr(health, "READINESS_TIMEOUT_SECONDS", 0.01)

    with TestClient(app) as client:
        response = client.get("/api/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Service is not ready"}
    assert response.headers["retry-after"] == "5"
    execute.assert_awaited_once()


def test_lifespan_disposes_database_engine(
    settings: Settings,
    lifecycle_engine: MagicMock,
) -> None:
    application = create_app(
        settings=settings,
        engine_factory=lambda _: cast(AsyncEngine, lifecycle_engine),
    )

    with TestClient(application):
        lifecycle_engine.dispose.assert_not_awaited()

    lifecycle_engine.dispose.assert_awaited_once_with()
