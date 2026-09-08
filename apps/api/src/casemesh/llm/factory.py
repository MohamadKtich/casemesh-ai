from casemesh.core.config import get_settings
from casemesh.llm.base import GenerationProvider
from casemesh.llm.huggingface import HuggingFaceGenerationProvider
from casemesh.llm.ollama import OllamaGenerationProvider


def get_generation_provider() -> GenerationProvider:
    settings = get_settings()

    if settings.generation_provider == "ollama":
        return OllamaGenerationProvider(
            base_url=settings.ollama_base_url,
            model=settings.generation_model,
            temperature=settings.generation_temperature,
            max_tokens=settings.generation_max_tokens,
        )

    if settings.generation_provider == "huggingface":
        return HuggingFaceGenerationProvider(
            model=settings.generation_model,
            temperature=settings.generation_temperature,
            max_tokens=settings.generation_max_tokens,
        )

    raise RuntimeError(
        f"Unsupported generation provider: {settings.generation_provider}"
    )