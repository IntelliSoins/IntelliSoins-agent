"""
Wrapper RAGAs-natif pour le serveur MLX d'embeddings local.

Appelle directement http://localhost:8084/v1/embeddings (API OpenAI-compatible
servie par mlx_lm.server / equivalent). Pas de dependance langchain-openai,
pas de tokenization tiktoken cote client, pas de modele charge in-process.

Le serveur sert le modele Qwen/Qwen3-Embedding-0.6B (1024D) qui doit etre
le MEME que celui ayant peuple document_embeddings.embedding (halfvec(1024)),
sinon les scores RAGAs context_precision/recall mesurent des espaces differents.
"""

from typing import List
import typing as t

import httpx
from ragas.embeddings.base import BaseRagasEmbeddings
from ragas.run_config import RunConfig


class MlxHttpEmbeddings(BaseRagasEmbeddings):
    """Client HTTP minimal pour mlx_lm.server embeddings (API OpenAI-compat)."""

    def __init__(
        self,
        base_url: str = "http://localhost:8084",
        model: str = "Qwen/Qwen3-Embedding-0.6B",
        timeout: float = 60.0,
        batch_size: int = 16,
    ):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.batch_size = batch_size
        self.run_config = RunConfig()
        self._sync_client = httpx.Client(timeout=timeout)
        self._async_client: httpx.AsyncClient | None = None

    def set_run_config(self, run_config: RunConfig) -> None:
        self.run_config = run_config

    def _post_sync(self, texts: List[str]) -> List[List[float]]:
        """Un seul batch d'inputs (batching applique par embed_documents)."""
        r = self._sync_client.post(
            f"{self.base_url}/v1/embeddings",
            json={"input": texts, "model": self.model},
        )
        r.raise_for_status()
        data = r.json()
        return [item["embedding"] for item in data["data"]]

    async def _post_async(self, texts: List[str]) -> List[List[float]]:
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(timeout=self.timeout)
        r = await self._async_client.post(
            f"{self.base_url}/v1/embeddings",
            json={"input": texts, "model": self.model},
        )
        r.raise_for_status()
        data = r.json()
        return [item["embedding"] for item in data["data"]]

    # --- Interface RAGAs ---

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            chunk = texts[i : i + self.batch_size]
            out.extend(self._post_sync(chunk))
        return out

    def embed_query(self, text: str) -> List[float]:
        return self._post_sync([text])[0]

    async def aembed_documents(self, texts: List[str]) -> t.List[t.List[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            chunk = texts[i : i + self.batch_size]
            out.extend(await self._post_async(chunk))
        return out

    async def aembed_query(self, text: str) -> List[float]:
        return (await self._post_async([text]))[0]
