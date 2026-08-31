from typing import Protocol


class EmbeddingProvider(Protocol):
    @property
    def model_name(self) -> str:
        """Return the configured embedding model name."""

    @property
    def dimension(self) -> int:
        """Return the embedding vector dimension."""

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed one or more texts."""

    async def health(self) -> dict[str, object]:
        """Return provider health information."""
