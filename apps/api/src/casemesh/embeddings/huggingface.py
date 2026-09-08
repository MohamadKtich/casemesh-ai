from typing import Any

import httpx


class HuggingFaceEmbeddingProvider:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        model: str,
        dimension: int,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token.strip()
        self._model = model
        self._dimension = dimension
        self._timeout_seconds = timeout_seconds

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        if not self._token:
            raise RuntimeError("Hugging Face token is not configured.")

        url = f"{self._base_url}/models/{self._model}"

        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

        payload = {
            "inputs": texts,
            "normalize": True,
            "truncate": True,
        }

        async with httpx.AsyncClient(
            timeout=self._timeout_seconds,
        ) as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
            )

        if not response.is_success:
            detail = response.text[:500]
            raise RuntimeError(
                "Hugging Face embedding request failed: "
                f"HTTP {response.status_code}: {detail}"
            )

        raw_payload: Any = response.json()

        if not isinstance(raw_payload, list):
            raise RuntimeError(
                "Hugging Face returned an invalid embedding payload."
            )

        # Some providers may return a single vector for one input.
        if raw_payload and all(
            isinstance(value, (int, float)) for value in raw_payload
        ):
            raw_embeddings = [raw_payload]
        else:
            raw_embeddings = raw_payload

        embeddings: list[list[float]] = []

        for raw_embedding in raw_embeddings:
            if not isinstance(raw_embedding, list):
                raise RuntimeError(
                    "Hugging Face returned an invalid embedding vector."
                )

            embedding = [float(value) for value in raw_embedding]

            if len(embedding) != self._dimension:
                raise RuntimeError(
                    "Embedding dimension mismatch: "
                    f"expected {self._dimension}, got {len(embedding)}."
                )

            embeddings.append(embedding)

        if len(embeddings) != len(texts):
            raise RuntimeError(
                "Embedding count mismatch: "
                f"expected {len(texts)}, got {len(embeddings)}."
            )

        return embeddings

    async def health(self) -> dict[str, object]:
        if not self._token:
            return {
                "status": "unavailable",
                "provider": "huggingface",
                "model": self._model,
                "dimension": self._dimension,
                "model_available": None,
                "detail": "Hugging Face token is not configured.",
            }

        try:
            embeddings = await self.embed_texts(
                ["CaseMesh embedding health check"]
            )
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            return {
                "status": "unavailable",
                "provider": "huggingface",
                "model": self._model,
                "dimension": self._dimension,
                "model_available": None,
                "detail": str(exc),
            }

        model_available = bool(
            embeddings
            and len(embeddings[0]) == self._dimension
        )

        return {
            "status": "ready" if model_available else "unavailable",
            "provider": "huggingface",
            "model": self._model,
            "dimension": self._dimension,
            "model_available": model_available,
            "detail": None,
        }