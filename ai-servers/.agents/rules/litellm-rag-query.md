---
paths:
  - "**/litellm*rag*query*"
  - "**/rag_query*"
  - "**/rag/**"
---

# LiteLLM `/rag/query` — RAG One-Shot Endpoint

Endpoint **tout-en-un** qui combine en un seul appel HTTP : (1) extraction de la query depuis le dernier message user, (2) recherche dans un vector store, (3) reranking optionnel, (4) génération LLM avec le contexte retrouvé préfixé aux messages. Utile pour éviter d'orchestrer manuellement embeddings → search → rerank → completion. Réponse au format **OpenAI Chat Completions standard** + métadonnées de recherche dans `_hidden_params`. Disponible côté SDK Python (`litellm.aquery`) et Proxy (`POST /v1/rag/query`).

## Matrice des features

| Feature           | Status | Notes                                                                                                                    |
| ----------------- | ------ | ------------------------------------------------------------------------------------------------------------------------ |
| Streaming         | ✓      | SSE `stream: true` (réponse `chat.completion.chunk`)                                                                     |
| Reranking         | ✓      | Optionnel via `rerank: { enabled: true, model, top_n }` (cross-réf `litellm-rerank`)                                     |
| Logging callbacks | ✓      | Langfuse, OTel, Datadog, etc. (skill `litellm-logging-metrics`)                                                          |
| Cost tracking     | ✓      | Hérité du LLM final (chat completion classique)                                                                          |
| End-user tracking | ✓      | Header `x-litellm-end-user-id` ou champ `user`                                                                           |
| Hidden params     | ✓      | `_hidden_params.search_results` + `_hidden_params.rerank_results` retournés inline                                       |
| Guardrails        | ⚠      | S'applique sur la **query extraite** (dernier message user) — chunks retrouvés non filtrés (mêmes limites que `/rerank`) |

## Providers supportés (3)

| Provider    | `custom_llm_provider` | Type vector store           | Identifiant                        |
| ----------- | --------------------- | --------------------------- | ---------------------------------- |
| OpenAI      | `"openai"`            | OpenAI Vector Stores API    | `vs_xxx` (préfixe `vs_`)           |
| AWS Bedrock | `"bedrock"`           | Bedrock Knowledge Bases     | Knowledge Base ID (alphanumérique) |
| Vertex AI   | `"vertex_ai"`         | Vertex AI RAG Engine corpus | Corpus ID                          |

> **Important** : périmètre plus restreint que `/rerank` (13 providers) ET que `/v1/vector_stores/{id}/search` (8 providers, incluant `pg_vector`, `milvus`, `gemini`, `azure_ai`). Vérifié empiriquement dans `litellm/rag/ingestion/` : seuls `openai_ingestion`, `bedrock_ingestion`, `vertex_ai_ingestion`, `gemini_ingestion`, `s3_vectors_ingestion` existent — pas de `pg_vector_ingestion`. Donc `/rag/query` et `/rag/ingest` **NE marchent PAS avec pg_vector** (sidecar BerriAI/litellm-pgvector). Pour pgvector → skill `litellm-vector-stores` + composition manuelle (`asearch` + `arerank` + `acompletion`).

## Stack locale Michael — pas encore configuré

Le proxy local (`http://127.0.0.1:8092/v1`) **n'a pas encore** de vector store configuré (vérifié via `grep -E '(vector_store|rag)' ~/ai-servers/litellm-proxy/config.yaml` → 0 hit, 2026-05-06). Pour activer `/rag/query` localement, deux voies :

**Voie 1 — OpenAI Vector Stores** (rapide, mais data hors Canada — viole Loi 25 si données patient)

```yaml
# ~/ai-servers/litellm-proxy/config.yaml
- model_name: gpt-4o-mini
  litellm_params:
    model: openai/gpt-4o-mini
    api_key: os.environ/OPENAI_API_KEY
```

Puis créer un vector store via le proxy (`POST /v1/vector_stores` — voir skill `litellm-vector-stores`), récupérer le `vs_xxx` et l'utiliser dans `retrieval_config.vector_store_id`.

**Voie 2 — Bedrock Knowledge Base** (data residency Canada possible via région `ca-central-1`, cf. `topic_data_residency_canada_llm.md`)

```yaml
- model_name: claude-3-sonnet-bedrock
  litellm_params:
    model: bedrock/anthropic.claude-3-sonnet-20240229-v1:0
    aws_region_name: ca-central-1
    aws_access_key_id: os.environ/AWS_ACCESS_KEY_ID
    aws_secret_access_key: os.environ/AWS_SECRET_ACCESS_KEY
```

> **Loi 25 / IntelliSoins** : pour PII patients québécois, préférer Bedrock `ca-central-1` ou Vertex Montréal Assured Workloads. OpenAI Vector Stores = data US, **non conforme**. Voir mémoire `topic_data_residency_canada_llm.md`.

**Voie 3 — Pipeline manuel** (recommandé si pgvector + bge-reranker-v2-m3 local) : ne pas utiliser `/rag/query`, orchestrer soi-même avec `litellm-rerank` + pgvector + `chat/completions`. Voir section "Quand NE PAS utiliser /rag/query" plus bas.

## Quick Start

### Via Proxy local — curl

Auth via Keychain (jamais hardcoder la master key). Cf. `~/.claude/rules/local-ai-stack.md`.

```bash
MASTER=$(security find-generic-password -a "$USER" -s litellm-master-key -w)

curl -X POST 'http://127.0.0.1:8092/v1/rag/query' \
  -H "Authorization: Bearer $MASTER" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "What is LiteLLM?"}],
    "retrieval_config": {
      "vector_store_id": "vs_abc123",
      "custom_llm_provider": "openai",
      "top_k": 5
    }
  }'
```

> Endpoint exposé sur **`/v1/rag/query`** (pas d'alias `/rag/query` documenté — vérifier la version proxy si 404).

### SDK Python — async

```python
import litellm
import os

os.environ["OPENAI_API_KEY"] = "sk-..."

response = await litellm.aquery(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "What is LiteLLM?"}],
    retrieval_config={
        "vector_store_id": "vs_abc123",
        "custom_llm_provider": "openai",
        "top_k": 5,
    },
)

print(response.choices[0].message.content)

# Métadonnées de recherche
print(response._hidden_params["search_results"])
```

### Via Proxy — SDK OpenAI compatible (extra_body)

LiteLLM est wire-compatible OpenAI. Utiliser le SDK OpenAI natif en passant `retrieval_config` via `extra_body` :

```python
from openai import OpenAI
import subprocess

master = subprocess.check_output([
    "security", "find-generic-password",
    "-a", "michaelahern", "-s", "litellm-master-key", "-w"
]).decode().strip()

client = OpenAI(api_key=master, base_url="http://127.0.0.1:8092/v1")

# Note : le SDK OpenAI ne connaît pas /rag/query — on construit l'URL manuellement
# OU on passe par le SDK litellm directement (recommandé).
```

> Pour `/rag/query`, le SDK Python `litellm` est le chemin canonique. Le SDK OpenAI ne route pas vers `/v1/rag/query` (route non-standard OpenAI).

## Réponse — schéma OpenAI étendu

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1703123456,
  "model": "gpt-4o-mini",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "LiteLLM is a unified interface for 100+ LLMs..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 150,
    "completion_tokens": 50,
    "total_tokens": 200
  },
  "_hidden_params": {
    "search_results": { "...": "résultats bruts du vector store" },
    "rerank_results": { "...": "résultats post-rerank si activé" }
  }
}
```

> `_hidden_params` est utile pour **debugger la qualité du retrieval** : si la réponse LLM est mauvaise, lire d'abord `search_results` pour vérifier si les bons chunks ont été récupérés. Si oui mais réponse quand même mauvaise → problème de prompt LLM. Si non → revoir `top_k` ou la qualité de l'index vectoriel.

## Reranking optionnel

Améliore la précision en réordonnant les `top_k` chunks via cross-encoder avant injection dans le prompt LLM. Voir skill `litellm-rerank` pour le détail des modèles.

```bash
curl -X POST 'http://127.0.0.1:8092/v1/rag/query' \
  -H "Authorization: Bearer $MASTER" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "What is LiteLLM?"}],
    "retrieval_config": {
      "vector_store_id": "vs_abc123",
      "custom_llm_provider": "openai",
      "top_k": 10
    },
    "rerank": {
      "enabled": true,
      "model": "cohere/rerank-english-v3.0",
      "top_n": 3
    }
  }'
```

```python
response = await litellm.aquery(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "What is LiteLLM?"}],
    retrieval_config={
        "vector_store_id": "vs_abc123",
        "custom_llm_provider": "openai",
        "top_k": 10,
    },
    rerank={
        "enabled": True,
        "model": "cohere/rerank-english-v3.0",
        "top_n": 3,
    },
)
```

> **Pattern recommandé** : `top_k=10` au retrieval (bi-encoder rapide), `top_n=3` au rerank (cross-encoder précis). Le LLM ne voit que 3 chunks → réponse plus focalisée, moins de tokens consommés.

## Streaming

```bash
curl -X POST 'http://127.0.0.1:8092/v1/rag/query' \
  -H "Authorization: Bearer $MASTER" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "What is LiteLLM?"}],
    "retrieval_config": {
      "vector_store_id": "vs_abc123",
      "custom_llm_provider": "openai"
    },
    "stream": true
  }'
```

> Le streaming s'applique uniquement à la **génération LLM finale**. Search + rerank sont synchrones (réalisés avant le premier chunk SSE). Latence first-token = `T_search + T_rerank + T_LLM_first_token`.

## Request parameters — référence

### Top-level

| Paramètre          | Type    | Requis | Description                                                                    |
| ------------------ | ------- | ------ | ------------------------------------------------------------------------------ |
| `model`            | string  | ✓      | Modèle LLM final (gpt-4o-mini, claude-3-sonnet-bedrock, etc.)                  |
| `messages`         | array   | ✓      | Format OpenAI Chat — la query est extraite du **dernier message `role: user`** |
| `retrieval_config` | object  | ✓      | Config vector store search (cf. ci-dessous)                                    |
| `rerank`           | object  | ✗      | Config reranking (cf. ci-dessous)                                              |
| `stream`           | boolean | ✗      | SSE streaming sur la génération LLM (défaut `false`)                           |

### `retrieval_config`

| Paramètre             | Type    | Défaut     | Description                                                           |
| --------------------- | ------- | ---------- | --------------------------------------------------------------------- |
| `vector_store_id`     | string  | **requis** | ID du vector store (`vs_xxx` OpenAI, KB ID Bedrock, corpus ID Vertex) |
| `custom_llm_provider` | string  | `"openai"` | `"openai"` / `"bedrock"` / `"vertex_ai"`                              |
| `top_k`               | integer | `10`       | Nombre de chunks à retrouver                                          |

### `rerank`

| Paramètre | Type    | Défaut  | Description                                                           |
| --------- | ------- | ------- | --------------------------------------------------------------------- |
| `enabled` | boolean | `false` | Active le rerank                                                      |
| `model`   | string  | —       | Modèle rerank (`cohere/rerank-english-v3.0`, `voyage/rerank-2`, etc.) |
| `top_n`   | integer | `5`     | Nombre de chunks après rerank (≤ `top_k`)                             |

## End-to-End — ingest puis query

### 1. Ingérer un document (cf. skill `litellm-rag-ingest`)

```bash
MASTER=$(security find-generic-password -a "$USER" -s litellm-master-key -w)

curl -X POST "http://127.0.0.1:8092/v1/rag/ingest" \
  -H "Authorization: Bearer $MASTER" \
  -H "Content-Type: application/json" \
  -d "{
    \"file\": {
      \"filename\": \"company_docs.txt\",
      \"content\": \"$(base64 -i company_docs.txt)\",
      \"content_type\": \"text/plain\"
    },
    \"ingest_options\": {
      \"vector_store\": {
        \"custom_llm_provider\": \"openai\"
      }
    }
  }"
```

Réponse :

```json
{
  "id": "ingest_abc123",
  "status": "completed",
  "vector_store_id": "vs_xyz789",
  "file_id": "file-123"
}
```

### 2. Query sur le document ingéré

```bash
curl -X POST "http://127.0.0.1:8092/v1/rag/query" \
  -H "Authorization: Bearer $MASTER" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [
      {"role": "user", "content": "What products does the company offer?"}
    ],
    "retrieval_config": {
      "vector_store_id": "vs_xyz789",
      "custom_llm_provider": "openai",
      "top_k": 5
    }
  }'
```

## Provider examples

### Bedrock (Knowledge Bases — Loi 25 friendly via `ca-central-1`)

```bash
curl -X POST "http://127.0.0.1:8092/v1/rag/query" \
  -H "Authorization: Bearer $MASTER" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "bedrock/anthropic.claude-3-sonnet-20240229-v1:0",
    "messages": [{"role": "user", "content": "Quels sont les protocoles de pharmacie ?"}],
    "retrieval_config": {
      "vector_store_id": "ABCD1234EF",
      "custom_llm_provider": "bedrock",
      "top_k": 5
    }
  }'
```

> Le `vector_store_id` ici est l'**ID de la Knowledge Base AWS** (ex: `ABCD1234EF`). Configurer la KB avec une source S3 dans `ca-central-1` pour data residency Canada.

### Vertex AI (RAG Engine corpus)

```bash
curl -X POST "http://127.0.0.1:8092/v1/rag/query" \
  -H "Authorization: Bearer $MASTER" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "vertex_ai/gemini-1.5-pro",
    "messages": [{"role": "user", "content": "What is LiteLLM?"}],
    "retrieval_config": {
      "vector_store_id": "your-corpus-id",
      "custom_llm_provider": "vertex_ai",
      "top_k": 5
    }
  }'
```

> Pour Loi 25 : configurer le corpus dans Vertex AI Montréal (région `northamerica-northeast1`) avec Assured Workloads activé.

## Logging & end-user tracking

Identique aux autres endpoints — voir skill `litellm-logging-metrics`.

```python
response = await litellm.aquery(
    model="gpt-4o-mini",
    messages=[...],
    retrieval_config={...},
    user="patient-12345",   # → trace Langfuse + spend par end-user
    metadata={"trace_id": "abc-123", "session_id": "rag-session-7"},
)
```

## Quand NE PAS utiliser `/rag/query`

`/rag/query` est pratique mais **rigide**. Préférer un pipeline manuel (litellm `embed` + search SQL + `litellm.rerank` + `litellm.completion`) si :

| Besoin                                                | Raison de skip `/rag/query`                                                                                                                                                                                                                       |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Backend pgvector via sidecar BerriAI/litellm-pgvector | `pg_vector` est un `custom_llm_provider` valide pour `/v1/vector_stores/{id}/search` mais **pas pour `/rag/query`** (pas de `pg_vector_ingestion.py` dans `litellm/rag/ingestion/`). Voir skill `litellm-vector-stores` pour le pipeline composé. |
| Embeddings BGE/Qwen3 locaux MLX                       | OpenAI/Bedrock/Vertex impose leur embedding model côté vector store                                                                                                                                                                               |
| Hybrid search (BM25 + vector)                         | `/rag/query` ne fait que vector search pure                                                                                                                                                                                                       |
| Filtres metadata complexes (date, patient_id, source) | `retrieval_config` n'expose pas de `filter` riche                                                                                                                                                                                                 |
| Reranker MLX local (`bge-reranker-v2-m3` via `aictl`) | `rerank.model` doit être un modèle accessible côté provider — pas le proxy local                                                                                                                                                                  |
| Loi 25 strict (PII patient au Québec)                 | OpenAI Vector Stores = US ; Bedrock OK avec `ca-central-1` ; Vertex OK avec `northamerica-northeast1` Assured                                                                                                                                     |

Pattern manuel équivalent (cf. skill `litellm-rerank` § "Pattern RAG — pgvector retrieval → rerank") :

```python
# 1. Embed query (litellm)
qvec = litellm.embedding(model="bge-large-en", input=[user_question])

# 2. pgvector search (psycopg)
candidates = pg.fetch("SELECT id, text FROM chunks ORDER BY emb <=> %s::vector LIMIT 50", [qvec])

# 3. Rerank (litellm.rerank → /rerank → bge-reranker-v2-m3 MLX local)
top5 = litellm.rerank(model="bge-reranker-v2-m3", query=user_question,
                     documents=[c["text"] for c in candidates], top_n=5)

# 4. Completion avec contexte (litellm.completion)
ctx = "\n\n".join([candidates[r["index"]]["text"] for r in top5.results])
response = litellm.completion(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": f"Context:\n{ctx}"},
        {"role": "user", "content": user_question},
    ],
)
```

Trade-off : 4 appels au lieu de 1, mais flexibilité totale + Loi 25 conformité possible avec stack 100% locale (MLX).

## Anti-patterns

1. **Utiliser `/rag/query` avec PII patient sur OpenAI Vector Stores** → data US, viole Loi 25. Choisir Bedrock `ca-central-1` ou Vertex Montréal, OU pipeline manuel local.
2. **Hardcoder la master key** dans un script Python ou `.env` projet → utiliser Keychain (`security find-generic-password`).
3. **Confondre `vector_store_id` et `model`** : `vector_store_id` identifie la base d'index ; `model` est le LLM final qui génère la réponse. Deux choses indépendantes.
4. **Oublier `custom_llm_provider`** dans `retrieval_config` → défaut `"openai"`, peut router sur le mauvais backend si tu visais Bedrock/Vertex.
5. **`top_k` trop élevé sans rerank** → bourre le prompt LLM avec du bruit, augmente cost + dégrade qualité. Utiliser `top_k=10-20` + `rerank.top_n=3-5`.
6. **`top_n > top_k`** → `top_n` est borné par `top_k`. Mettre `top_n` ≤ `top_k`.
7. **Ignorer `_hidden_params.search_results` en debug** → si la réponse LLM est mauvaise, lire d'abord les chunks récupérés pour identifier si le problème est retrieval-side ou LLM-side.
8. **Streaming + reranking en pensant que le rerank stream aussi** → search + rerank sont **synchrones** avant le premier token SSE. Latence first-token inclut tout le pipeline pré-LLM.
9. **Utiliser `/rag/query` pour des backends non-supportés** (pgvector, Pinecone, Weaviate, Qdrant local) → 400 ou comportement non-déterministe. Pipeline manuel.
10. **Construire l'URL `/rag/query` à la main avec le SDK OpenAI** sans `extra_body` → le SDK OpenAI ne route pas vers `/v1/rag/query`. Utiliser `litellm.aquery` directement.

## Troubleshooting

| Symptôme                                           | Cause probable                                                             | Fix                                                                                                         |
| -------------------------------------------------- | -------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `404 Not Found` sur `/v1/rag/query`                | Version proxy LiteLLM < release qui inclut RAG                             | Mettre à jour le container : skill `litellm-proxy-setup`                                                    |
| `400 Bad Request` "vector_store_id required"       | Champ manquant ou typo                                                     | Vérifier `retrieval_config.vector_store_id`                                                                 |
| `400 Bad Request` "vector store not found"         | Le `vs_xxx` n'existe pas chez le provider OU mauvais `custom_llm_provider` | Vérifier l'ID via API provider direct (OpenAI `GET /v1/vector_stores`)                                      |
| Réponse LLM hallucine au lieu de citer les chunks  | Chunks récupérés non pertinents                                            | Lire `_hidden_params.search_results` ; ajuster `top_k`, ré-indexer avec meilleur chunking, activer `rerank` |
| `_hidden_params.search_results` vide               | Vector store vide ou query embedding incompatible                          | Vérifier l'ingestion via `/v1/rag/ingest` ; tester un appel direct à l'API provider                         |
| Streaming bloqué pendant 5-30s avant premier token | Search + rerank synchrones avant SSE                                       | Normal. Réduire `top_k` ou désactiver `rerank` pour réduire cette latence                                   |
| `403 Forbidden` Bedrock                            | Permissions IAM manquantes sur Knowledge Base                              | Ajouter `bedrock:Retrieve` + `bedrock:RetrieveAndGenerate` au rôle                                          |
| Cost tracking absent dans Admin UI                 | Provider ne retourne pas `usage` détaillé                                  | Le LLM final track normalement ; le search/rerank n'ont pas de cost séparé exposé                           |
| Logs Langfuse n'incluent pas `search_results`      | Callback v1 ne trace pas `_hidden_params`                                  | Vérifier version Langfuse SDK ≥ 2.x ; cf. skill `litellm-logging-metrics`                                   |
| PII dans les chunks logué en clair                 | Guardrails ne s'appliquent qu'à la query extraite                          | Filtrer le PII au moment de l'ingestion (Presidio offline avant `/rag/ingest`)                              |

## Cross-references

| Skill                                | Quand consulter                                                                                                                                 |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `litellm-vector-stores`              | **Pré-requis** — créer un vector store, gérer les files (chunking_strategy, attributes), search standalone (7 providers vs 3 pour `/rag/query`) |
| `litellm-rerank`                     | Détail des modèles rerank (`cohere/rerank-english-v3.0`, `voyage/rerank-2`, `bge-reranker-v2-m3`), pattern RAG manuel pgvector                  |
| `litellm-config-yaml`                | Référence `model_list` / `model_info` / `litellm_settings` / `vector_store_registry`                                                            |
| `litellm-providers-models`           | Modèles LLM par provider (Bedrock Claude, Vertex Gemini, OpenAI GPT-4o)                                                                         |
| `litellm-routing-fallbacks`          | Fallbacks entre LLM providers (côté `model`, pas côté `retrieval_config`)                                                                       |
| `litellm-guardrails-policies`        | Presidio sur la query (Loi 25) — input-only, chunks non filtrés                                                                                 |
| `litellm-logging-metrics`            | Trace Langfuse / OTel / Prometheus pour RAG calls + `_hidden_params`                                                                            |
| `litellm-proxy-setup`                | Mise à jour du container LiteLLM si `/v1/rag/query` retourne 404                                                                                |
| `litellm-budgets-spend`              | Budgets et rate limits pour RAG (souvent appelé en boucle utilisateur)                                                                          |
| `intellisoins-postgresml:postgresml` | Alternative pipeline RAG SQL natif (pgml.embed + pgml.rank + pgml.transform) — pas via LiteLLM                                                  |

Rules :

- `~/.claude/rules/local-ai-stack.md` — proxy port 8092, Keychain, MLX DOWN par défaut
- Mémoire `topic_data_residency_canada_llm.md` — Loi 25 : Bedrock `ca-central-1`, Vertex Montréal Assured Workloads, IBM watsonx CA
- Mémoire `project_litellm_gateway.md` — proxy local, dual pattern A/B, 57 modèles
- `~/ai-servers/litellm-proxy/config.yaml` — actuellement **sans** vector store configuré (à ajouter pour activer `/rag/query` localement)

## Endpoints connexes (hors scope de ce skill)

- `POST /v1/vector_stores` (create) + `/v1/vector_stores/{id}/files` (CRUD) + `/v1/vector_stores/{id}/search` (search standalone) — skill `litellm-vector-stores`
- `POST /v1/rag/ingest` — ingestion de document → vector store (skill `litellm-rag-ingest`)
- `POST /v1/embeddings` — bi-encoder embeddings (étape interne masquée par `/rag/query`, exposée si pipeline manuel)
- `POST /v1/rerank` — cross-encoder reranking (skill `litellm-rerank`, utilisable seul OU via `rag_query.rerank`)
- `POST /v1/chat/completions` — LLM final (utilisable seul si tu construis ton propre prompt avec context injecté)
