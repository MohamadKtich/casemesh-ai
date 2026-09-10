import json

import pytest

from casemesh.mcp.auth import BearerTokenAuthMiddleware


def make_http_scope(
    authorization: str | None = None,
) -> dict:
    headers: list[tuple[bytes, bytes]] = []

    if authorization is not None:
        headers.append(
            (
                b"authorization",
                authorization.encode("utf-8"),
            )
        )

    return {
        "type": "http",
        "asgi": {
            "version": "3.0",
        },
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/mcp/",
        "raw_path": b"/mcp/",
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": (
            "127.0.0.1",
            12345,
        ),
        "server": (
            "127.0.0.1",
            8000,
        ),
    }


async def receive() -> dict:
    return {
        "type": "http.request",
        "body": b"",
        "more_body": False,
    }


def response_status(
    messages: list[dict],
) -> int:
    start = next(
        message
        for message in messages
        if message["type"] == "http.response.start"
    )

    return start["status"]


def response_body(
    messages: list[dict],
) -> dict:
    body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )

    return json.loads(
        body.decode("utf-8")
    )


@pytest.mark.asyncio
async def test_non_http_scope_bypasses_auth() -> None:
    called = False

    async def app(
        scope,
        receive,
        send,
    ) -> None:
        nonlocal called
        called = True

    middleware = BearerTokenAuthMiddleware(
        app,
        token="",
    )

    scope = {
        "type": "lifespan",
    }

    async def dummy_receive() -> dict:
        return {
            "type": "lifespan.startup",
        }

    async def dummy_send(message: dict) -> None:
        return None

    await middleware(
        scope,
        dummy_receive,
        dummy_send,
    )

    assert called is True


@pytest.mark.asyncio
async def test_missing_configured_token_returns_503() -> None:
    called = False
    messages: list[dict] = []

    async def app(
        scope,
        receive,
        send,
    ) -> None:
        nonlocal called
        called = True

    async def send(message: dict) -> None:
        messages.append(message)

    middleware = BearerTokenAuthMiddleware(
        app,
        token="",
    )

    await middleware(
        make_http_scope(),
        receive,
        send,
    )

    assert called is False
    assert response_status(messages) == 503

    assert response_body(messages) == {
        "detail": "MCP authentication is not configured."
    }


@pytest.mark.asyncio
async def test_missing_authorization_returns_401() -> None:
    called = False
    messages: list[dict] = []

    async def app(
        scope,
        receive,
        send,
    ) -> None:
        nonlocal called
        called = True

    async def send(message: dict) -> None:
        messages.append(message)

    middleware = BearerTokenAuthMiddleware(
        app,
        token="secret-token",
    )

    await middleware(
        make_http_scope(),
        receive,
        send,
    )

    assert called is False
    assert response_status(messages) == 401

    assert response_body(messages) == {
        "detail": "Unauthorized"
    }


@pytest.mark.asyncio
async def test_wrong_auth_scheme_returns_401() -> None:
    called = False
    messages: list[dict] = []

    async def app(
        scope,
        receive,
        send,
    ) -> None:
        nonlocal called
        called = True

    async def send(message: dict) -> None:
        messages.append(message)

    middleware = BearerTokenAuthMiddleware(
        app,
        token="secret-token",
    )

    await middleware(
        make_http_scope(
            "Basic secret-token"
        ),
        receive,
        send,
    )

    assert called is False
    assert response_status(messages) == 401


@pytest.mark.asyncio
async def test_wrong_bearer_token_returns_401() -> None:
    called = False
    messages: list[dict] = []

    async def app(
        scope,
        receive,
        send,
    ) -> None:
        nonlocal called
        called = True

    async def send(message: dict) -> None:
        messages.append(message)

    middleware = BearerTokenAuthMiddleware(
        app,
        token="secret-token",
    )

    await middleware(
        make_http_scope(
            "Bearer wrong-token"
        ),
        receive,
        send,
    )

    assert called is False
    assert response_status(messages) == 401


@pytest.mark.asyncio
async def test_valid_bearer_token_calls_protected_app() -> None:
    called = False
    messages: list[dict] = []

    async def app(
        scope,
        receive,
        send,
    ) -> None:
        nonlocal called
        called = True

        await send(
            {
                "type": "http.response.start",
                "status": 204,
                "headers": [],
            }
        )

        await send(
            {
                "type": "http.response.body",
                "body": b"",
            }
        )

    async def send(message: dict) -> None:
        messages.append(message)

    middleware = BearerTokenAuthMiddleware(
        app,
        token="secret-token",
    )

    await middleware(
        make_http_scope(
            "Bearer secret-token"
        ),
        receive,
        send,
    )

    assert called is True
    assert response_status(messages) == 204


@pytest.mark.asyncio
async def test_bearer_scheme_is_case_insensitive() -> None:
    called = False
    messages: list[dict] = []

    async def app(
        scope,
        receive,
        send,
    ) -> None:
        nonlocal called
        called = True

        await send(
            {
                "type": "http.response.start",
                "status": 204,
                "headers": [],
            }
        )

        await send(
            {
                "type": "http.response.body",
                "body": b"",
            }
        )

    async def send(message: dict) -> None:
        messages.append(message)

    middleware = BearerTokenAuthMiddleware(
        app,
        token="secret-token",
    )

    await middleware(
        make_http_scope(
            "bEaReR   secret-token"
        ),
        receive,
        send,
    )

    assert called is True
    assert response_status(messages) == 204
