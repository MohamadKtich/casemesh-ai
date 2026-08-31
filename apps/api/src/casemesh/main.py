from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from casemesh.api.router import api_router
from casemesh.core.config import get_settings
from casemesh.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "application_starting",
        app_name=settings.app_name,
        app_version=settings.app_version,
        environment=settings.app_env,
    )
    yield
    logger.info("application_stopping")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="CaseMesh AI case investigation and resolution API",
    lifespan=lifespan,
)

app.include_router(api_router)


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
    }
