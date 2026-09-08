import hmac

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class BearerTokenAuthMiddleware:
    """
    Protect an ASGI application with a static bearer token.

    This middleware is intentionally fail-closed:
    if no token is configured, requests are rejected instead
    of exposing the protected application anonymously.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        token: str,
    ) -> None:
        self._app = app
        self._token = token.strip()

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self._app(
                scope,
                receive,
                send,
            )
            return

        if not self._token:
            response = JSONResponse(
                {
                    "detail": (
                        "MCP authentication is not configured."
                    )
                },
                status_code=503,
            )
            await response(
                scope,
                receive,
                send,
            )
            return

        headers = Headers(scope=scope)
        authorization = headers.get(
            "authorization",
            "",
        )

        scheme, separator, credential = authorization.partition(" ")

        valid = (
            bool(separator)
            and scheme.casefold() == "bearer"
            and bool(credential)
            and hmac.compare_digest(
                credential.strip(),
                self._token,
            )
        )

        if not valid:
            response = JSONResponse(
                {
                    "detail": "Unauthorized",
                },
                status_code=401,
                headers={
                    "WWW-Authenticate": "Bearer",
                },
            )
            await response(
                scope,
                receive,
                send,
            )
            return

        await self._app(
            scope,
            receive,
            send,
        )