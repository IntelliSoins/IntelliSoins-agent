## Pattern — Wrapper RAGAs natif pour MLX (sans langchain-openai)

Pour utiliser RAGAs avec un serveur MLX local, **subclasser directement** `BaseRagasEmbeddings` au lieu de `LangchainEmbeddingsWrapper(OpenAIEmbeddings(...))`. Évite le bug tiktoken, ~30 lignes, réutilisable pour BGE rerank et tout serveur OpenAI-compat.

```python
from ragas.embeddings.base import BaseRagasEmbeddings
from ragas.run_config import RunConfig
import httpx

class MlxHttpEmbeddings(BaseRagasEmbeddings):
    def __init__(self, base_url="http://localhost:8084",
                 model="Qwen/Qwen3-Embedding-0.6B", batch_size=16):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.batch_size = batch_size
        self.run_config = RunConfig()
        self._sync = httpx.Client(timeout=60.0)
        self._async = None  # lazy init

    def set_run_config(self, rc: RunConfig): self.run_config = rc

    def _post_sync(self, texts):
        r = self._sync.post(f"{self.base_url}/v1/embeddings",
                            json={"input": texts, "model": self.model})
        r.raise_for_status()
        return [d["embedding"] for d in r.json()["data"]]

    def embed_documents(self, texts):
        out = []
        for i in range(0, len(texts), self.batch_size):
            out.extend(self._post_sync(texts[i:i+self.batch_size]))
        return out
    def embed_query(self, text): return self._post_sync([text])[0]
    # aembed_documents / aembed_query : symétriques avec httpx.AsyncClient
```

**Implémentation de référence** : `~/ai-servers/scripts/mlx_embeddings_client.py` (testée 2026-05-11 sur ragas 0.2.10 + Python 3.12).

**Cohérence d'espace d'embedding** : critique. Si la DB cible utilise un modèle pour indexer ses chunks (ex: `Qwen/Qwen3-Embedding-0.6B` 1024D sur `:8084` pour `document_embeddings.embedding halfvec(1024)`), le wrapper RAGAs doit utiliser **exactement le même modèle**. Sinon les métriques `context_precision` et `context_recall` mesurent des espaces différents.
