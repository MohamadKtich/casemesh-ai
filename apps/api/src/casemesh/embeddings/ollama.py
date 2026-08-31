from typing import Any

import httpx


class OllamaEmbeddingProvider:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        dimension: int,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
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

        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout_seconds,
        ) as client:
            response = await client.post(
                "/api/embed",
                json={
                    "model": self._model,
                    "input": texts,
                    "truncate": True,
                },
            )

        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        raw_embeddings = payload.get("embeddings")

        if not isinstance(raw_embeddings, list):
            raise RuntimeError("Ollama returned no embeddings.")

        embeddings: list[list[float]] = []
        for raw_embedding in raw_embeddings:
            if not isinstance(raw_embedding, list):
                raise RuntimeError("Ollama returned an invalid embedding payload.")

            embedding = [float(value) for value in raw_embedding]
            if len(embedding) != self._dimension:
                raise RuntimeError(
                    "Embedding dimension mismatch: "
                    f"expected {self._dimension}, got {len(embedding)}."
                )
            embeddings.append(embedding)

        if len(embeddings) != len(texts):
            raise RuntimeError(
                f"Embedding count mismatch: expected {len(texts)}, got {len(embeddings)}."
            )

        return embeddings

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
                "provider": "ollama",
                "model": self._model,
                "dimension": self._dimension,
                "detail": str(exc),
            }

        models = payload.get("models", [])
        installed_names = {
            str(model.get("name", "")).split(":", maxsplit=1)[0]
            for model in models
            if isinstance(model, dict)
        }
        model_available = self._model.split(":", maxsplit=1)[0] in installed_names

        return {
            "status": "ready" if model_available else "model_missing",
            "provider": "ollama",
            "model": self._model,
            "dimension": self._dimension,
            "model_available": model_available,
        }
