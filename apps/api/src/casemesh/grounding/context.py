from dataclasses import dataclass
from uuid import UUID

from casemesh.schemas.retrieval import RetrievalResult


@dataclass(frozen=True)
class EvidenceSource:
    label: str
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    metadata_json: dict[str, object]


class EvidenceContextBuilder:
    def __init__(
        self,
        *,
        max_context_chars: int,
        max_source_chars: int,
    ) -> None:
        self._max_context_chars = max_context_chars
        self._max_source_chars = max_source_chars

    def build(
        self,
        results: list[RetrievalResult],
    ) -> list[EvidenceSource]:
        sources: list[EvidenceSource] = []
        consumed = 0

        for index, result in enumerate(results, start=1):
            remaining = self._max_context_chars - consumed
            if remaining <= 0:
                break

            source_limit = min(self._max_source_chars, remaining)
            content = result.content[:source_limit].strip()
            if not content:
                continue

            sources.append(
                EvidenceSource(
                    label=f"E{index}",
                    chunk_id=result.chunk_id,
                    document_id=result.document_id,
                    chunk_index=result.chunk_index,
                    content=content,
                    metadata_json=result.metadata_json,
                )
            )
            consumed += len(content)

        return sources

    def render(self, sources: list[EvidenceSource]) -> str:
        blocks: list[str] = []

        for source in sources:
            blocks.append(
                "\n".join(
                    [
                        f"SOURCE [{source.label}]",
                        f"chunk_id: {source.chunk_id}",
                        f"document_id: {source.document_id}",
                        f"chunk_index: {source.chunk_index}",
                        "content:",
                        source.content,
                    ]
                )
            )

        return "\n\n".join(blocks)
