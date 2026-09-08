import os
from typing import Any

import httpx


class HuggingFaceGenerationProvider:
    def __init__(
        self,
        *,
        model: str,
        temperature: float,
        max_tokens: int,
        base_url: str = "https://router.huggingface.co/v1",
        timeout_seconds: float = 180.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout_seconds = timeout_seconds

    @property
    def provider_name(self) -> str:
        return "huggingface"

    @property
    def model_name(self) -> str:
        return self._model

    def _token(self) -> str:
        token = os.getenv("HF_TOKEN", "").strip()
        if not token:
            raise RuntimeError("HF_TOKEN is not configured.")
        return token

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        token = self._token()

        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout_seconds,
            headers={
                "Authorization": f"Bearer {token}",
            },
        ) as client:
            response = await client.post(
                "/chat/completions",
                json={
                    "model": self._model,
                    "messages": [
                        {
                            "role": "system",
                            "content": system_prompt,
                        },
                        {
                            "role": "user",
                            "content": user_prompt,
                        },
                    ],
                    "temperature": self._temperature,
                    "max_tokens": self._max_tokens,
                },
            )

        response.raise_for_status()

        payload: dict[str, Any] = response.json()

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("Hugging Face returned no completion choices.")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise RuntimeError("Hugging Face returned an invalid completion choice.")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("Hugging Face returned no message object.")

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Hugging Face returned an empty generation.")

        return content.strip()

    async def health(self) -> dict[str, object]:
        token_available = bool(os.getenv("HF_TOKEN", "").strip())

        return {
            "status": "ready" if token_available else "unavailable",
            "provider": self.provider_name,
            "model": self._model,
            "model_available": token_available,
            "detail": None if token_available else "HF_TOKEN is not configured.",
        }