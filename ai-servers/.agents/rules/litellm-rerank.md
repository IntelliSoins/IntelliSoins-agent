---
paths:
  - "**/litellm*rerank*"
  - "**/rerank*"
  - "**/cross_encoder*"
  - "**/cohere_rerank*"
---

# LiteLLM `/rerank` — Cross-Encoder Reranking

Endpoint compatible API Cohere pour réordonner une liste de documents en fonction d'une query, en retournant un score de pertinence et l'index original. Utile en **deuxième étape** d'un pipeline RAG (après recherche vectorielle / BM25) pour améliorer la précision top-k avec un cross-encoder. Disponible côté SDK Python (`litellm.rerank`) et Proxy (`POST /rerank` ou `POST /v1/rerank`).

## Matrice des features

| Feature           | Status | Notes                                                                                 |
| ----------------- | ------ | ------------------------------------------------------------------------------------- |
| Cost tracking     | ✓      | Tous providers supportés                                                              |
| Logging callbacks | ✓      | Langfuse, OTel, Datadog, etc. (skill `litellm-logging-metrics`)                       |
| End-user tracking | ✓      | Header `x-litellm-end-user-id` ou champ `user`                                        |
| Fallbacks         | ✓      | Par requête (`extra_body`) ou via `litellm_settings.fallbacks`                        |
| Loadbalancing     | ✓      | Plusieurs deployments avec même `model_name`                                          |
| Guardrails        | ⚠      | **Input query seulement** — les `documents` ne sont pas filtrés (limitation upstream) |
| Streaming         | ✗      | N/A pour rerank (réponse synchrone unique)                                            |

## Providers supportés (13)

`cohere` (v1 + v2), `together_ai`, `azure_ai`, `jina_ai`, `bedrock`, `huggingface`, `infinity`, `vllm`, `deepinfra`, `vertex_ai`, `fireworks_ai`, `voyage_ai`, `watsonx`.

> Voir la liste complète à jour : <https://models.litellm.ai/> (filter `mode=rerank`).

## Stack locale Michael — modèle déjà configuré

Le proxy local (`http://127.0.0.1:8092/v1`) expose déjà :

```yaml
# ~/ai-servers/litellm-proxy/config.yaml:199-203
- model_name: bge-reranker-v2-m3
  litellm_params:
    model: openai/bge-reranker-v2-m3
    api_base: http://127.0.0.1:8085/v1 # backend MLX local (mlx-omni-server)
    api_key: dummy
```

> **Backend DOWN par défaut.** Avant de rerank : `aictl start bge-reranker-v2-m3`.
> Cf. `~/.claude/rules/local-ai-stack.md` et skill `intellisoins-infrastructure:local-ai-servers`.

Pour activer explicitement le routing `/rerank` et le cost tracking, ajouter le mode :

```yaml
- model_name: bge-reranker-v2-m3
  litellm_params:
    model: openai/bge-reranker-v2-m3
    api_base: http://127.0.0.1:8085/v1
    api_key: dummy
  model_info:
    mode: rerank # CRITIQUE — active la route /rerank dans le router
```

Sans `mode: rerank` dans `model_info`, LiteLLM peut router la requête sur `chat/completions` selon le call type → 4xx obscur.

## Quick Start

### SDK Python — sync

```python
from litellm import rerank
import os

os.environ["COHERE_API_KEY"] = "sk-..."

response = rerank(
    model="cohere/rerank-english-v3.0",
    query="What is the capital of the United States?",
    documents=[
        "Carson City is the capital city of the American state of Nevada.",
        "The Commonwealth of the Northern Mariana Islands is in the Pacific Ocean. Its capital is Saipan.",
        "Washington, D.C. is the capital of the United States.",
        "Capital punishment has existed in the United States since before it was a country.",
    ],
    top_n=3,
)

# response.results = [{"index": 2, "relevance_score": 0.99}, {"index": 0, "relevance_score": 0.31}, ...]
for r in response.results:
    print(r["index"], r["relevance_score"])
```

### SDK Python — async

```python
from litellm import arerank
import asyncio

async def go():
    return await arerank(
        model="cohere/rerank-english-v3.0",
        query="What is the capital of the United States?",
        documents=[...],
        top_n=3,
    )

asyncio.run(go())
```

### Via Proxy local (recommandé — tracking + fallbacks)

Auth via Keychain (jamais hardcoder la master key). Cf. `local-ai-stack.md`.

```bash
MASTER=$(security find-generic-password -a "$USER" -s litellm-master-key -w)

curl -X POST 'http://127.0.0.1:8092/rerank' \
  -H "Authorization: Bearer $MASTER" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "bge-reranker-v2-m3",
    "query": "What is the capital of the United States?",
    "documents": [
        "Carson City is the capital city of the American state of Nevada.",
        "Washington, D.C. is the capital of the United States.",
        "Capital punishment has existed in the United States since before it was a country."
    ],
    "top_n": 3
  }'
```

> Endpoint exposé sur **`/rerank`** (et alias `/v1/rerank`). Format : JSON, pas multipart.

### Via Proxy + client Cohere SDK

LiteLLM est wire-compatible Cohere v1 et v2 — utiliser le SDK Cohere natif en pointant `api_url` vers le proxy.

```python
import cohere, subprocess

master = subprocess.check_output([
    "security", "find-generic-password",
    "-a", "michaelahern", "-s", "litellm-master-key", "-w"
]).decode().strip()

# v2 client (recommandé)
co = cohere.ClientV2(api_key=master, base_url="http://127.0.0.1:8092")
resp = co.rerank(
    model="bge-reranker-v2-m3",
    query="What is the capital of the United States?",
    documents=["...", "..."],
    top_n=3,
)
```

## Pattern RAG — pgvector retrieval → rerank

Use case typique IntelliSoins : retrieval HNSW retourne top-50 candidats, on rerank pour ne garder que top-5 vraiment pertinents.

```python
from openai import OpenAI
import subprocess, requests

master = subprocess.check_output(
    ["security", "find-generic-password", "-a", "michaelahern", "-s", "litellm-master-key", "-w"]
).decode().strip()

# 1. Retrieval pgvector (top-50)
candidates = pg_conn.fetch("""
  SELECT id, chunk_text, embedding <=> $1::vector AS distance
  FROM rag_chunks
  ORDER BY distance ASC LIMIT 50
""", query_embedding)

# 2. Rerank via LiteLLM (top-5)
rerank_resp = requests.post(
    "http://127.0.0.1:8092/rerank",
    headers={"Authorization": f"Bearer {master}"},
    json={
        "model": "bge-reranker-v2-m3",
        "query": user_question,
        "documents": [c["chunk_text"] for c in candidates],
        "top_n": 5,
    },
).json()

# 3. Reconstruire l'ordre via index original
top5 = [candidates[r["index"]] for r in rerank_resp["results"]]
```

> Pourquoi rerank après retrieval ? Le bi-encoder (embeddings) est rapide mais imprécis ; le cross-encoder (rerank) est lent mais précis. Combo retrieval (50→top) + rerank (5→top) = précision ~90% du cross-encoder pur, latence ~1/10ᵉ.

## Fallbacks

Deux niveaux : par-requête (override ad-hoc) et global (config proxy).

### Fallback par requête — Python SDK

```python
from litellm import rerank

response = rerank(
    model="bge-reranker-v2-m3",   # primary local MLX
    query="...",
    documents=[...],
    top_n=3,
    fallbacks=["cohere/rerank-english-v3.0", "voyage/rerank-2"],
)
```

Si `bge-reranker-v2-m3` retourne 5xx ou timeout (backend MLX DOWN, OOM), LiteLLM retry sur `cohere/rerank-english-v3.0` puis `voyage/rerank-2`. Cost tracking attribué au modèle qui a effectivement répondu.

### Fallback par requête — curl

```bash
curl -X POST 'http://127.0.0.1:8092/rerank' \
  -H "Authorization: Bearer $MASTER" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "bge-reranker-v2-m3",
    "query": "...",
    "documents": [...],
    "top_n": 3,
    "fallbacks": ["cohere/rerank-english-v3.0", "voyage/rerank-2"]
  }'
```

### Fallback global — config proxy

```yaml
# config.yaml
litellm_settings:
  fallbacks:
    - bge-reranker-v2-m3: ["cohere/rerank-english-v3.0", "voyage/rerank-2"]
```

Cf. skill `litellm-routing-fallbacks` pour `context_window`, `content_policy`, retries, cooldowns, priority-ordered deployments.

### Tester la chaîne sans casser le primary

`mock_testing_fallbacks=True` force un échec simulé du primary → la chaîne s'exécute. Utile en CI.

```python
response = rerank(
    model="bge-reranker-v2-m3",
    query="...",
    documents=[...],
    top_n=3,
    fallbacks=["cohere/rerank-english-v3.0"],
    mock_testing_fallbacks=True,
)
# bge-reranker-v2-m3 mock-failed → réponse vient de cohere/rerank-english-v3.0
```

## Config provider-spécifique

### Cohere (v1 + v2 — référence API)

```yaml
- model_name: rerank-english-v3.0
  litellm_params:
    model: cohere/rerank-english-v3.0
    api_key: os.environ/COHERE_API_KEY
  model_info:
    mode: rerank
```

Modèles : `rerank-english-v3.0`, `rerank-multilingual-v3.0`, `rerank-v3.5` (latest).

### Together AI

```yaml
- model_name: llama-rank
  litellm_params:
    model: together_ai/Salesforce/Llama-Rank-V1
    api_key: os.environ/TOGETHERAI_API_KEY
  model_info:
    mode: rerank
```

### Voyage AI (recommandé pour multilingue + qualité haute)

```yaml
- model_name: voyage-rerank
  litellm_params:
    model: voyage/rerank-2
    api_key: os.environ/VOYAGE_API_KEY
  model_info:
    mode: rerank
```

Modèles : `rerank-2`, `rerank-2-lite`, `rerank-lite-1`. Jusqu'à 16K tokens par document — utile pour chunks longs.

### Jina AI

```yaml
- model_name: jina-rerank
  litellm_params:
    model: jina_ai/jina-reranker-v2-base-multilingual
    api_key: os.environ/JINA_AI_API_KEY
  model_info:
    mode: rerank
```

### AWS Bedrock

```yaml
- model_name: bedrock-rerank
  litellm_params:
    model: bedrock/cohere.rerank-v3-5:0
    aws_region_name: us-west-2
  model_info:
    mode: rerank
```

### Azure AI

```yaml
- model_name: azure-rerank
  litellm_params:
    model: azure_ai/cohere-rerank-v3-multilingual
    api_base: os.environ/AZURE_AI_API_BASE
    api_key: os.environ/AZURE_AI_API_KEY
  model_info:
    mode: rerank
```

### Vertex AI

```yaml
- model_name: vertex-rerank
  litellm_params:
    model: vertex_ai/semantic-ranker-default-004
    vertex_project: os.environ/VERTEX_PROJECT
    vertex_location: us-central1
  model_info:
    mode: rerank
```

### HuggingFace TEI / Infinity / vLLM (self-hosted)

Tous trois exposent une API rerank compatible. Pattern identique au backend MLX local :

```yaml
- model_name: hf-rerank-tei
  litellm_params:
    model: huggingface/BAAI/bge-reranker-v2-m3
    api_base: http://127.0.0.1:8090 # endpoint TEI
    api_key: dummy
  model_info:
    mode: rerank

- model_name: infinity-rerank
  litellm_params:
    model: infinity/mixedbread-ai/mxbai-rerank-large-v1
    api_base: http://127.0.0.1:7997
    api_key: dummy
  model_info:
    mode: rerank
```

### IBM watsonx.ai (data residency CA via watsonx Toronto)

```yaml
- model_name: watsonx-rerank
  litellm_params:
    model: watsonx/cross-encoder/ms-marco-minilm-l-12-v2
    api_key: os.environ/WATSONX_API_KEY
    project_id: os.environ/WATSONX_PROJECT_ID
  model_info:
    mode: rerank
```

> Voir mémoire `topic_data_residency_canada_llm.md` — watsonx CA est une option souveraine pour Loi 25.

## Loadbalancing entre déploiements

Plusieurs entrées avec le même `model_name` → LiteLLM round-robin / least-busy.

```yaml
- model_name: bge-rerank-pool
  litellm_params:
    model: openai/bge-reranker-v2-m3
    api_base: http://127.0.0.1:8085/v1
    api_key: dummy
  model_info:
    mode: rerank

- model_name: bge-rerank-pool
  litellm_params:
    model: huggingface/BAAI/bge-reranker-v2-m3
    api_base: http://gpu-server.intellisoins.local:8090
    api_key: os.environ/HF_TEI_KEY
  model_info:
    mode: rerank
```

Cf. skill `litellm-routing-fallbacks` pour stratégies (`simple-shuffle`, `least-busy`, `latency-based`, `cost-based`).

## Cost tracking

Cost tracking automatique pour les providers qui retournent un `usage` dans la réponse. Pour les backends locaux sans usage info, configurer manuellement :

```yaml
- model_name: bge-reranker-v2-m3
  litellm_params:
    model: openai/bge-reranker-v2-m3
    api_base: http://127.0.0.1:8085/v1
    api_key: dummy
  model_info:
    mode: rerank
    input_cost_per_query: 0.0 # local = gratuit
    input_cost_per_document: 0.0
```

## Logging & end-user tracking

Identique aux autres endpoints — voir skill `litellm-logging-metrics`.

```python
response = rerank(
    model="bge-reranker-v2-m3",
    query="...",
    documents=[...],
    top_n=3,
    user="patient-12345",   # → trace Langfuse + spend par end-user
    metadata={"trace_id": "abc-123", "session_id": "rag-session-7"},
)
```

## Guardrails — input query uniquement

⚠️ **Limitation upstream documentée** : les guardrails (Presidio PII, Lakera, AIM, etc.) s'appliquent **uniquement sur l'input `query`**, pas sur les `documents`. Si une query contient du PII (ex: nom patient, NAS), il sera masqué avant envoi au reranker. Mais si les documents contiennent du PII, ils passent intacts.

```yaml
guardrails:
  - guardrail_name: presidio-pii-query
    litellm_params:
      guardrail: presidio
      mode: pre_call
      apply_to:
        - bge-reranker-v2-m3
        - cohere/rerank-english-v3.0
```

Implication Loi 25 / IntelliSoins : si les chunks indexés contiennent du PII (résumés cliniques, dossiers patients), le PII est exposé au reranker — choisir un reranker **on-prem** (`bge-reranker-v2-m3` MLX local) plutôt qu'un cloud non-souverain. Voir skill `litellm-guardrails-policies` pour le détail des modes (`pre_call` / `during_call` / `post_call`).

## Anti-patterns

1. **Oublier `mode: rerank`** dans `model_info` → router peut envoyer sur `chat/completions` → 4xx obscur ou réponse vide.
2. **Hardcoder la master key** dans un script Python ou `.env` projet → utiliser Keychain (`security find-generic-password`).
3. **Appeler `bge-reranker-v2-m3` sans `aictl start`** → backend MLX DOWN par défaut, requête timeout.
4. **Confondre embedding et rerank** : embedding (bi-encoder) retourne un vecteur ; rerank (cross-encoder) retourne un score query↔document. Ne pas remplacer l'un par l'autre.
5. **Rerank sans retrieval préalable** → cross-encoder est O(n) sur documents, ne pas l'utiliser pour scanner 1M docs. Toujours retrieval (HNSW/IVF) avant rerank.
6. **Documents vides ou trop longs** : la plupart des modèles tronquent à 512 tokens (BGE) ou 16K (Voyage). Documents plus longs = perte de signal sur la fin. Chunker avant.
7. **Mélanger `extra_body.fallbacks` (par requête) et `litellm_settings.fallbacks` (global)** sans comprendre la précédence → la valeur par requête écrase la valeur globale pour cette requête.
8. **Compter sur les guardrails pour filtrer du PII dans les `documents`** → ne s'applique qu'à `query`. Pour PII dans les chunks : filtrer en amont au moment de l'indexation.

## Troubleshooting

| Symptôme                                               | Cause probable                                                                  | Fix                                                                           |
| ------------------------------------------------------ | ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `404 Not Found` sur `/rerank`                          | `mode: rerank` manquant dans `model_info`                                       | Ajouter dans config.yaml + restart proxy                                      |
| `400 Bad Request` "documents required"                 | Champ `documents` vide ou mal nommé                                             | Vérifier JSON : `"documents": ["...", "..."]` (array de strings)              |
| Timeout sur `bge-reranker-v2-m3` local                 | Backend MLX DOWN                                                                | `aictl start bge-reranker-v2-m3` puis `aictl status`                          |
| Scores tous à 0.5 ± 0.05                               | Documents tronqués (>512 tokens)                                                | Chunker plus court ou utiliser `voyage/rerank-2` (16K tokens)                 |
| Fallback ne se déclenche pas                           | Le primary retourne 200 avec `results: []` → pas considéré comme failure        | Ajouter health check upstream (skill `litellm-routing-fallbacks` § cooldowns) |
| Cost tracking absent dans Admin UI                     | Provider ne retourne pas `usage`                                                | Configurer `model_info.input_cost_per_query` manuellement                     |
| PII dans les documents apparaît dans les logs          | Guardrails ne s'appliquent qu'à `query`                                         | Filtrer le PII au moment de l'ingestion (Presidio offline avant index)        |
| `cohere.RerankResponse` vide après LiteLLM v1.x → v2.x | Migration v1→v2 client Cohere : champ `results[].relevance_score` (pas `score`) | Utiliser `r["relevance_score"]` ou `r.relevance_score` selon SDK              |

## Cross-references

| Skill                                          | Quand consulter                                                              |
| ---------------------------------------------- | ---------------------------------------------------------------------------- |
| `litellm-routing-fallbacks`                    | Fallbacks avancés, cooldowns, retries, A/B testing, loadbalancing strategies |
| `litellm-config-yaml`                          | Référence complète `model_list` / `model_info` / `litellm_settings`          |
| `litellm-guardrails-policies`                  | Presidio/Lakera sur la query (Loi 25) — limitation input-only                |
| `litellm-logging-metrics`                      | Trace Langfuse / OTel / Prometheus pour rerank calls                         |
| `litellm-providers-models`                     | Liste exhaustive des modèles rerank par provider                             |
| `litellm-budgets-spend`                        | Budgets et rate limits pour rerank (souvent appelé en boucle RAG)            |
| `intellisoins-infrastructure:local-ai-servers` | Gestion `aictl` pour démarrer `bge-reranker-v2-m3`                           |
| `intellisoins-mlx:mlx-embeddings`              | Modèles d'embeddings MLX en amont du rerank                                  |
| `intellisoins-postgresml:postgresml`           | Alternative `pgml.rank()` SQL — rerank in-database (pas via LiteLLM)         |

Rules :

- `~/.claude/rules/local-ai-stack.md` — proxy port 8092, Keychain, MLX DOWN par défaut, 22 modèles
- `~/.claude/rules/postgresml-usage.md` — `pgml.rank` cross-encoder reranking SQL alternatif
- `~/ai-servers/litellm-proxy/config.yaml:199-203` — config `bge-reranker-v2-m3` actuelle

## Endpoints connexes (hors scope de ce skill)

- `/v1/embeddings` — bi-encoder embeddings (étape précédant le rerank dans un RAG)
- `/v1/chat/completions` — LLM final consommant les top-k post-rerank

À couvrir dans des skills séparés (`litellm-embeddings` futur, ou skill projet RAG dédié).
