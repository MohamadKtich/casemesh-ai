from casemesh.core.config import get_settings
from casemesh.embeddings.base import EmbeddingProvider
from casemesh.embeddings.huggingface import HuggingFaceEmbeddingProvider
from casemesh.embeddings.ollama import OllamaEmbeddingProvider


def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()

    if settings.embedding_provider == "ollama":
        return OllamaEmbeddingProvider(
            base_url=settings.ollama_base_url,
            model=settings.embedding_model,
            dimension=settings.embedding_dimension,
        )

    if settings.embedding_provider == "huggingface":
        return HuggingFaceEmbeddingProvider(
            base_url=settings.hf_inference_base_url,
            token=settings.hf_token,
            model=settings.embedding_model,
            dimension=settings.embedding_dimension,
        )

    raise RuntimeError(
        f"Unsupported embedding provider: {settings.embedding_provider}"
    )