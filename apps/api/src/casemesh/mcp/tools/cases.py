from uuid import UUID

from mcp.server import MCPServer

from casemesh.db.session import AsyncSessionLocal
from casemesh.repositories.cases import CaseRepository


def register_case_tools(server: MCPServer) -> None:
    @server.tool()
    async def get_case_status(
        case_id: str,
    ) -> dict[str, object]:
        """
        Read the current status and basic metadata for a CaseMesh case.

        This tool is read-only and never modifies case data.
        """
        try:
            parsed_case_id = UUID(case_id)
        except ValueError:
            return {
                "found": False,
                "error": "invalid_case_id",
                "message": "case_id must be a valid UUID.",
            }

        async with AsyncSessionLocal() as session:
            repository = CaseRepository(session)

            case = await repository.get(parsed_case_id)

            if case is None:
                return {
                    "found": False,
                    "case_id": case_id,
                    "error": "case_not_found",
                    "message": "No CaseMesh case exists with this case_id.",
                }

            return {
                "found": True,
                "case_id": str(case.id),
                "case_number": case.case_number,
                "title": case.title,
                "status": case.status,
                "priority": case.priority,
                "customer_ref": case.customer_ref,
                "updated_at": case.updated_at.isoformat(),
            }