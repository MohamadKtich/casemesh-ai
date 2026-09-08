from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.transport_security import TransportSecuritySettings

from casemesh.api.router import api_router
from casemesh.core.config import get_settings
from casemesh.core.logging import configure_logging, get_logger
from casemesh.mcp.auth import BearerTokenAuthMiddleware
from casemesh.mcp.server import server as mcp_server


settings = get_settings()

configure_logging(settings.log_level)
logger = get_logger(__name__)


def build_cors_allowed_origins() -> list[str]:
    origins: list[str] = []

    for raw_origin in settings.cors_allowed_origins.split(","):
        origin = raw_origin.strip().rstrip("/")

        if origin and origin not in origins:
            origins.append(origin)

    return origins


def build_mcp_transport_security() -> TransportSecuritySettings:
    allowed_hosts = [
        "localhost",
        "localhost:*",
        "127.0.0.1",
        "127.0.0.1:*",
    ]

    allowed_origins: list[str] = []

    public_hostname = settings.mcp_public_hostname.strip()

    if public_hostname:
        allowed_hosts.extend(
            [
                public_hostname,
                f"{public_hostname}:*",
            ]
        )

        allowed_origins.append(
            f"https://{public_hostname}"
        )

    return TransportSecuritySettings(
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


cors_allowed_origins = build_cors_allowed_origins()

mcp_transport_security = build_mcp_transport_security()

mcp_http_app = mcp_server.streamable_http_app(
    streamable_http_path="/",
    transport_security=mcp_transport_security,
)

mcp_protected_app = BearerTokenAuthMiddleware(
    mcp_http_app,
    token=settings.mcp_auth_token,
)


@asynccontextmanager
async def lifespan(
    _: FastAPI,
) -> AsyncIterator[None]:
    logger.info(
        "application_starting",
        app_name=settings.app_name,
        app_version=settings.app_version,
        environment=settings.app_env,
        cors_allowed_origins=cors_allowed_origins,
    )

    async with mcp_server.session_manager.run():
        yield

    logger.info("application_stopping")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="CaseMesh AI case investigation and resolution API",
    lifespan=lifespan,
)

if cors_allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allowed_origins,
        allow_credentials=False,
        allow_methods=[
            "GET",
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
            "OPTIONS",
        ],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept",
        ],
    )

app.include_router(api_router)

app.mount(
    "/mcp",
    mcp_protected_app,
    name="mcp",
)


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
        "mcp": "/mcp/",
    }