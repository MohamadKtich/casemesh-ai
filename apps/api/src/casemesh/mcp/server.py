from mcp.server import MCPServer

from casemesh.mcp.tools import (
    register_case_tools,
    register_evidence_tools,
)

server = MCPServer(
    name="casemesh-mcp",
    title="CaseMesh AI MCP Server",
    description=(
        "Read-only MCP interface for governed access "
        "to CaseMesh AI case data and grounded evidence."
    ),
    instructions=(
        "Use CaseMesh tools to inspect case information "
        "and search grounded case evidence. "
        "These tools are read-only unless explicitly "
        "documented otherwise."
    ),
)

register_case_tools(server)
register_evidence_tools(server)