from uuid import UUID

from fastapi import HTTPException
from mcp.server import MCPServer

from casemesh.db.session import AsyncSessionLocal
from casemesh.embeddings.factory import get_embedding_provider
from casemesh.repositories.cases import CaseRepository
from casemesh.repositories.documents import DocumentRepository
from casemesh.repositories.retrieval import RetrievalRepository
from casemesh.services.retrieval import RetrievalService


def register_evidence_tools(server: MCPServer) -> None:
    @server.tool()
    async def search_case_evidence(
        case_id: str,
        query: str,
        top_k: int = 5,
    ) -> dict[str, object]:
        """
        Search grounded evidence for a CaseMesh case.

        Uses the existing CaseMesh hybrid retrieval pipeline:
        vector similarity + PostgreSQL keyword search + RRF fusion.

        This tool is read-only.
        """
        try:
            parsed_case_id = UUID(case_id)
        except ValueError:
            return {
                "found": False,
                "error": "invalid_case_id",
                "message": "case_id must be a valid UUID.",
            }

        clean_query = query.strip()

        if not clean_query:
            return {
                "found": False,
                "error": "empty_query",
                "message": "query must not be empty.",
            }

        if top_k < 1 or top_k > 10:
            return {
                "found": False,
                "error": "invalid_top_k",
                "message": "top_k must be between 1 and 10.",
            }

        async with AsyncSessionLocal() as session:
            service = RetrievalService(
                case_repository=CaseRepository(session),
                document_repository=DocumentRepository(session),
                retrieval_repository=RetrievalRepository(session),
                embedding_provider=get_embedding_provider(),
            )

            try:
                response = await service.search(
                    case_id=parsed_case_id,
                    query=clean_query,
                    top_k=top_k,
                )
            except HTTPException as exc:
                return {
                    "found": False,
                    "error": "retrieval_error",
                    "status_code": exc.status_code,
                    "message": str(exc.detail),
                }
            except RuntimeError as exc:
                return {
                    "found": False,
                    "error": "provider_error",
                    "message": str(exc),
                }

        results = [
            {
                "chunk_id": str(item.chunk_id),
                "document_id": str(item.document_id),
                "chunk_index": item.chunk_index,
                "content": item.content,
                "metadata": item.metadata_json,
                "hybrid_score": item.hybrid_score,
                "vector_rank": item.vector_rank,
                "keyword_rank": item.keyword_rank,
                "vector_similarity": item.vector_similarity,
                "keyword_score": item.keyword_score,
            }
            for item in response.results
        ]

        return {
            "found": bool(results),
            "case_id": case_id,
            "query": response.query,
            "top_k": response.top_k,
            "mode": "hybrid_rrf",
            "embedding_model": response.embedding_model,
            "result_count": len(results),
            "results": results,
        }