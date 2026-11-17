"""Liveness and readiness probes."""

import asyncio
import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from cybersentinel_backend import __version__
from cybersentinel_backend.database import get_database_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])
READINESS_TIMEOUT_SECONDS = 3.0


class HealthResponse(BaseModel):
    """Stable response schema shared by health endpoints."""

    status: Literal["ok", "ready"]
    version: str


@router.get("/live", response_model=HealthResponse, summary="Check process liveness")
async def liveness() -> HealthResponse:
    """Confirm that the API process can serve requests."""

    return HealthResponse(status="ok", version=__version__)


@router.get(
    "/ready",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Database unavailable"}},
    summary="Check service readiness",
)
async def readiness(
    engine: Annotated[AsyncEngine, Depends(get_database_engine)],
) -> HealthResponse:
    """Confirm that the API can execute a query against PostgreSQL."""

    try:
        async with asyncio.timeout(READINESS_TIMEOUT_SECONDS):
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
    except Exception:
        logger.warning("Database readiness check failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is not ready",
            headers={"Retry-After": "5"},
        ) from None

    return HealthResponse(status="ready", version=__version__)
