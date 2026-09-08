from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from casemesh.mcp.client import CaseMeshMcpClient
from casemesh.schemas.retrieval import RetrievalSearchResponse


class McpRetrievalService:
    def __init__(
        self,
        *,
        client: CaseMeshMcpClient,
    ) -> None:
        self._client = client

    async def search(
        self,
        *,
        case_id: UUID,
        query: str,
        top_k: int,
    ) -> RetrievalSearchResponse:
        try:
            payload = await self._client.search_case_evidence(
                case_id=str(case_id),
                query=query,
                top_k=top_k,
            )
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"MCP retrieval unavailable: {exc}",
            ) from exc

        if payload.get("error"):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(
                    payload.get(
                        "message",
                        "MCP retrieval failed.",
                    )
                ),
            )

        raw_results = payload.get("results", [])

        if not isinstance(raw_results, list):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="MCP returned invalid retrieval results.",
            )

        normalized_results: list[dict[str, Any]] = []

        for item in raw_results:
            if not isinstance(item, dict):
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="MCP returned an invalid evidence item.",
                )

            normalized_results.append(
                {
                    "chunk_id": item.get("chunk_id"),
                    "document_id": item.get("document_id"),
                    "chunk_index": item.get("chunk_index"),
                    "content": item.get("content", ""),
                    "metadata_json": item.get(
                        "metadata",
                        {},
                    ),
                    "hybrid_score": item.get(
                        "hybrid_score",
                        0.0,
                    ),
                    "vector_rank": item.get(
                        "vector_rank",
                    ),
                    "keyword_rank": item.get(
                        "keyword_rank",
                    ),
                    "vector_similarity": item.get(
                        "vector_similarity",
                    ),
                    "keyword_score": item.get(
                        "keyword_score",
                    ),
                }
            )

        return RetrievalSearchResponse.model_validate(
            {
                "query": payload.get(
                    "query",
                    query,
                ),
                "top_k": payload.get(
                    "top_k",
                    top_k,
                ),
                "mode": payload.get(
                    "mode",
                    "hybrid_rrf",
                ),
                "embedding_model": payload.get(
                    "embedding_model",
                    "unknown",
                ),
                "results": normalized_results,
            }
        )