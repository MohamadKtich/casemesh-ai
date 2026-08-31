from typing import Any

import httpx


class OllamaGenerationProvider:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        temperature: float,
        max_tokens: int,
        timeout_seconds: float = 180.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout_seconds = timeout_seconds

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout_seconds,
        ) as client:
            response = await client.post(
                "/api/chat",
                json={
                    "model": self._model,
                    "stream": False,
                    "think": False,
                    "format": "json",
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
                    "options": {
                        "temperature": self._temperature,
                        "num_predict": self._max_tokens,
                    },
                },
            )

        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        message = payload.get("message")

        if not isinstance(message, dict):
            raise RuntimeError("Ollama returned no message object.")

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Ollama returned an empty generation.")

        return content.strip()

    async def health(self) -> dict[str, object]:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=10.0,
            ) as client:
                response = await client.get("/api/tags")
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
        except httpx.HTTPError as exc:
            return {
                "status": "unavailable",
                "provider": self.provider_name,
                "model": self._model,
                "model_available": False,
                "detail": str(exc),
            }

        models = payload.get("models", [])
        configured_base = self._model.split(":", maxsplit=1)[0]
        installed_bases = {
            str(model.get("name", "")).split(":", maxsplit=1)[0]
            for model in models
            if isinstance(model, dict)
        }
        model_available = configured_base in installed_bases

        return {
            "status": "ready" if model_available else "model_missing",
            "provider": self.provider_name,
            "model": self._model,
            "model_available": model_available,
            "detail": None,
        }
