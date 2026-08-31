from casemesh.core.config import get_settings
from casemesh.embeddings.base import EmbeddingProvider
from casemesh.embeddings.ollama import OllamaEmbeddingProvider


def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()

    if settings.embedding_provider == "ollama":
        return OllamaEmbeddingProvider(
            base_url=settings.ollama_base_url,
            model=settings.embedding_model,
            dimension=settings.embedding_dimension,
        )

    raise RuntimeError(f"Unsupported embedding provider: {settings.embedding_provider}")
