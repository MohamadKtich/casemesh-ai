from __future__ import annotations

import asyncio
import sys

import uvicorn


HOST = "127.0.0.1"
PORT = 8000
APP = "casemesh.main:app"


async def serve() -> None:
    loop = asyncio.get_running_loop()

    print("=" * 60)
    print("CaseMesh AI API")
    print(f"Platform   : {sys.platform}")
    print(f"Event loop : {type(loop).__name__}")
    print(f"Address    : http://{HOST}:{PORT}")
    print(f"Swagger    : http://{HOST}:{PORT}/docs")
    print("=" * 60)

    config = uvicorn.Config(
        app=APP,
        host=HOST,
        port=PORT,
        log_level="info",
        access_log=True,
    )

    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    if sys.platform == "win32":
        # Psycopg async connections are not compatible with
        # Windows ProactorEventLoop.
        #
        # Create the API's actual running loop explicitly as a
        # SelectorEventLoop instead of merely changing the global
        # event-loop policy.
        with asyncio.Runner(
            loop_factory=asyncio.SelectorEventLoop,
        ) as runner:
            runner.run(serve())
        return

    asyncio.run(serve())


if __name__ == "__main__":
    main()