from typing import Protocol


class GenerationProvider(Protocol):
    @property
    def provider_name(self) -> str:
        """Return the provider identifier."""

    @property
    def model_name(self) -> str:
        """Return the configured generation model."""

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Generate a non-streaming text response."""

    async def health(self) -> dict[str, object]:
        """Return provider and model health information."""
