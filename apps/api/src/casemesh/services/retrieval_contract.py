from typing import Protocol
from uuid import UUID

from casemesh.schemas.retrieval import RetrievalSearchResponse


class RetrievalSearcher(Protocol):
    async def search(
        self,
        *,
        case_id: UUID,
        query: str,
        top_k: int,
    ) -> RetrievalSearchResponse:
        """Search case evidence and return normalized retrieval results."""