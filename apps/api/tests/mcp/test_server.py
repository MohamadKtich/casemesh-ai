from casemesh.mcp import server as exported_server
from casemesh.mcp.server import server


def test_mcp_package_exports_server() -> None:
    assert exported_server is server
