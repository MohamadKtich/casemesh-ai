import asyncio

from casemesh.mcp.server import server


async def main() -> None:
    await server.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())