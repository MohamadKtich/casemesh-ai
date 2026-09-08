from uuid import UUID

from fastapi import HTTPException, status

from casemesh.mcp.client import CaseMeshMcpClient
from casemesh.services.case_reader import CaseSnapshot


class McpCaseReader:
    def __init__(
        self,
        *,
        client: CaseMeshMcpClient,
    ) -> None:
        self._client = client

    async def get(
        self,
        case_id: UUID,
    ) -> CaseSnapshot | None:
        try:
            payload = await self._client.get_case_status(
                case_id=str(case_id),
            )
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"MCP case lookup unavailable: {exc}",
            ) from exc

        if not payload.get("found"):
            if payload.get("error") == "case_not_found":
                return None

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(
                    payload.get(
                        "message",
                        "MCP case lookup failed.",
                    )
                ),
            )

        try:
            payload_case_id = UUID(
                str(payload["case_id"])
            )

            case_number = str(
                payload["case_number"]
            )

            title = str(
                payload["title"]
            )

            case_status = str(
                payload["status"]
            )

            priority = str(
                payload["priority"]
            )

            customer_ref_raw = payload.get(
                "customer_ref"
            )

            customer_ref = (
                None
                if customer_ref_raw is None
                else str(customer_ref_raw)
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "MCP returned an invalid case payload."
                ),
            ) from exc

        return CaseSnapshot(
            id=payload_case_id,
            case_number=case_number,
            title=title,
            status=case_status,
            priority=priority,
            customer_ref=customer_ref,
        )