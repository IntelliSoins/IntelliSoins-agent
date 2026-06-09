---
paths:
  - "**/litellm*rag*ingest*"
  - "**/rag_ingest*"
  - "**/chunk*pipeline*"
---

# LiteLLM `/rag/ingest` — Pipeline d'ingestion documentaire

Endpoint unifié qui exécute en une seule requête : upload du fichier → chunking → embedding → écriture dans le vector store. Disponible côté Proxy (`POST /v1/rag/ingest`). Support natif cost tracking, logging, auto-provisioning de l'infra cloud (Bedrock KB, S3 buckets, OpenSearch collections).

> **Aval du pipeline** : `/v1/rag/query` (génère une réponse LLM augmentée) ou `/v1/vector_stores/{id}/search` (search direct, pas de génération). Couverts dans skills séparés.

## Matrice des features

| Feature                    | Status    | Notes                                                                   |
| -------------------------- | --------- | ----------------------------------------------------------------------- |
| Cost tracking              | ✓         | Embedding + storage attribués au modèle utilisé                         |
| Logging callbacks          | ✓         | Langfuse, OTel, Datadog, etc. (via `litellm-logging-metrics`)           |
| Auto-création vector store | ✓         | Tous providers sauf Vertex AI (corpus pré-créé requis)                  |
| Chunking server-side       | ⚠         | Vertex AI uniquement (`chunking_strategy` honoré côté serveur)          |
| Multi-input                | ✓         | `file` (base64) OU `file_url` OU `file_id` existant                     |
| Wait-for-indexing          | ✓         | Bedrock (`wait_for_ingestion`), Vertex (`wait_for_import`)              |
| Custom embedding model     | ✓ partiel | S3 Vectors (any LiteLLM model) ; OpenAI/Bedrock/Vertex imposent le leur |

## Providers supportés

`openai`, `bedrock`, `vertex_ai`, `gemini`, `s3_vectors`.

| Provider     | Vector store                           | Embedding par défaut                  | Auto-création                            |
| ------------ | -------------------------------------- | ------------------------------------- | ---------------------------------------- |
| `openai`     | OpenAI vector store (`vs_*`)           | `text-embedding-3-small` (imposé)     | Oui (omettre `vector_store_id`)          |
| `bedrock`    | Knowledge Base + OpenSearch Serverless | `amazon.titan-embed-text-v2:0`        | Oui (full stack S3 + IAM + KB)           |
| `vertex_ai`  | RAG Corpus                             | `text-embedding-004` (imposé)         | **Non** — corpus + GCS bucket pré-requis |
| `gemini`     | (cf. provider config)                  | (cf. provider config)                 | (cf. provider config)                    |
| `s3_vectors` | S3 vector bucket + index               | **Custom** (auto-detection dimension) | Oui (bucket + index)                     |

## Stack locale Michael — RAG souverain

Le proxy local (`http://127.0.0.1:8092/v1`) expose déjà :

```yaml
# ~/ai-servers/litellm-proxy/config.yaml:193-203
- model_name: qwen3-embedding # 1024D, port 8084 (MLX)
  litellm_params:
    model: openai/qwen3-embedding
    api_base: http://127.0.0.1:8084/v1
    api_key: dummy

- model_name: bge-reranker-v2-m3 # rerank, port 8085 (MLX)
  litellm_params:
    model: openai/bge-reranker-v2-m3
    api_base: http://127.0.0.1:8085/v1
    api_key: dummy
```

**Combinaisons RAG possibles depuis le proxy local** :

| Cas                                | Vector store                                        | Embedding                        | Souveraineté                                            |
| ---------------------------------- | --------------------------------------------------- | -------------------------------- | ------------------------------------------------------- |
| **A. RAG cloud OpenAI**            | `openai` (cloud)                                    | `text-embedding-3-small` (cloud) | ❌ Non (cloud US)                                       |
| **B. RAG souverain local**         | `s3_vectors` (cloud US) + `qwen3-embedding` (local) | `qwen3-embedding` 1024D          | ⚠ Partiel — embeddings locaux mais index sur AWS        |
| **C. RAG Bedrock auto**            | `bedrock` (cloud US)                                | `titan-embed-text-v2:0`          | ❌ Non (cloud US)                                       |
| **D. RAG full-local hors LiteLLM** | pgvector (Postgres17 local) + `qwen3-embedding`     | `qwen3-embedding` direct         | ✓ Oui (cf. skill `intellisoins-mlx:apple-data-indexer`) |

> **Loi 25 / IntelliSoins** : aucun des 5 providers `/rag/ingest` n'offre data-in-use Canada par défaut. Pour souveraineté complète, sortir de `/rag/ingest` et utiliser le pipeline Postgres17 + pgvector + `qwen3-embedding` direct (skill `apple-data-indexer`). Voir `~/.claude/projects/-Users-michaelahern-ai-servers/memory/topic_data_residency_canada_llm.md`.

> **Backend MLX DOWN par défaut.** Avant d'utiliser cas B/D : `aictl start qwen3-embedding`.

## Quick Start

### OpenAI (auto-création vector store)

```bash
MASTER=$(security find-generic-password -a "$USER" -s litellm-master-key -w)

curl -X POST "http://127.0.0.1:8092/v1/rag/ingest" \
  -H "Authorization: Bearer $MASTER" \
  -H "Content-Type: application/json" \
  -d "{
    \"file\": {
      \"filename\": \"document.txt\",
      \"content\": \"$(base64 -i document.txt)\",
      \"content_type\": \"text/plain\"
    },
    \"ingest_options\": {
      \"name\": \"test-basic-ingest\",
      \"vector_store\": {
        \"custom_llm_provider\": \"openai\"
      }
    }
  }"
```

Réponse :

```json
{
  "id": "ingest_d834f544-fc5e-4751-902d-fb0bcc183b85",
  "status": "completed",
  "vector_store_id": "vs_692658d337c4819183f2ad8488d12fc9",
  "file_id": "file-M2pJJiWH56cfUP4Fe7rJay"
}
```

### Bedrock Knowledge Base (auto-provisioning full stack)

```bash
curl -X POST "http://127.0.0.1:8092/v1/rag/ingest" \
  -H "Authorization: Bearer $MASTER" \
  -H "Content-Type: application/json" \
  -d "{
    \"file\": {
      \"filename\": \"document.txt\",
      \"content\": \"$(base64 -i document.txt)\",
      \"content_type\": \"text/plain\"
    },
    \"ingest_options\": {
      \"vector_store\": {
        \"custom_llm_provider\": \"bedrock\",
        \"wait_for_ingestion\": true,
        \"ingestion_timeout\": 600
      }
    }
  }"
```

> **Premier appel = ~5-10 min** : LiteLLM crée S3 bucket + OpenSearch Serverless collection + IAM role + Knowledge Base + Data Source. Activer `wait_for_ingestion: true` sinon `status: "pending"` retourné avant que les embeddings soient indexés.

### Vertex AI RAG Engine (corpus pré-existant requis)

```bash
curl -X POST "http://127.0.0.1:8092/v1/rag/ingest" \
  -H "Authorization: Bearer $MASTER" \
  -H "Content-Type: application/json" \
  -d "{
    \"file\": {
      \"filename\": \"document.txt\",
      \"content\": \"$(base64 -i document.txt)\",
      \"content_type\": \"text/plain\"
    },
    \"ingest_options\": {
      \"chunking_strategy\": {
        \"chunk_size\": 500,
        \"chunk_overlap\": 100
      },
      \"vector_store\": {
        \"custom_llm_provider\": \"vertex_ai\",
        \"vector_store_id\": \"projects/XXX/locations/us-central1/ragCorpora/YYY\",
        \"gcs_bucket\": \"intellisoins-rag-uploads\"
      }
    }
  }"
```

> Vertex AI **n'auto-crée pas** le corpus. Pré-requis : (1) RAG corpus créé via console/API, (2) GCS bucket pour upload, (3) `gcloud auth application-default login`, (4) `uv add 'google-cloud-aiplatform>=1.60.0'` côté proxy.

### S3 Vectors avec embedding custom (cas B local)

```bash
curl -X POST "http://127.0.0.1:8092/v1/rag/ingest" \
  -H "Authorization: Bearer $MASTER" \
  -H "Content-Type: application/json" \
  -d "{
    \"file\": {
      \"filename\": \"document.txt\",
      \"content\": \"$(base64 -i document.txt)\",
      \"content_type\": \"text/plain\"
    },
    \"ingest_options\": {
      \"embedding\": {
        \"model\": \"qwen3-embedding\"
      },
      \"vector_store\": {
        \"custom_llm_provider\": \"s3_vectors\",
        \"vector_bucket_name\": \"intellisoins-embeddings\",
        \"distance_metric\": \"cosine\",
        \"aws_region_name\": \"us-west-2\"
      }
    }
  }"
```

> **Auto-detection dimension** : LiteLLM fait un test embedding sur `qwen3-embedding` (→ 1024D), crée l'index S3 Vectors avec la bonne dimension, puis ingère. Pas besoin de `dimension` manuel.

### Python (via OpenAI SDK)

```python
import base64, subprocess, requests

master = subprocess.check_output([
    "security", "find-generic-password",
    "-a", "michaelahern", "-s", "litellm-master-key", "-w"
]).decode().strip()

with open("/path/to/doc.pdf", "rb") as f:
    content_b64 = base64.b64encode(f.read()).decode()

response = requests.post(
    "http://127.0.0.1:8092/v1/rag/ingest",
    headers={"Authorization": f"Bearer {master}", "Content-Type": "application/json"},
    json={
        "file": {
            "filename": "doc.pdf",
            "content": content_b64,
            "content_type": "application/pdf",
        },
        "ingest_options": {
            "name": "intellisoins-pubmed-corpus",
            "chunking_strategy": {"chunk_size": 800, "chunk_overlap": 150},
            "vector_store": {"custom_llm_provider": "openai"},
        },
    },
)
print(response.json())
```

## Modes d'input (3 alternatives)

Exactement un de `file`, `file_url`, `file_id` doit être fourni.

### `file` — base64 inline

```json
{
  "file": {
    "filename": "doc.pdf",
    "content": "<base64-encoded-bytes>",
    "content_type": "application/pdf"
  }
}
```

Utiliser pour fichiers <10MB. Au-delà, payload trop lourd → préférer `file_url`.

### `file_url` — fetch depuis URL

```json
{
  "file_url": "https://example.com/document.pdf"
}
```

LiteLLM télécharge côté proxy. Utile pour corpus déjà hébergé (S3 public, GCS, CDN). L'URL doit être accessible depuis l'hôte du proxy.

### `file_id` — réutiliser un upload existant

```json
{
  "file_id": "file-M2pJJiWH56cfUP4Fe7rJay"
}
```

L'`id` retourné par un précédent appel `/files` ou `/rag/ingest`. Permet d'ingérer le même document dans plusieurs vector stores sans re-uploader.

## Chunking Strategy

Contrôle la découpe avant embedding. Spécifié dans `ingest_options.chunking_strategy`.

| Param           | Type | Défaut | Description                           |
| --------------- | ---- | ------ | ------------------------------------- |
| `chunk_size`    | int  | `1000` | Taille max d'un chunk (caractères)    |
| `chunk_overlap` | int  | `200`  | Recouvrement entre chunks consécutifs |

> **Server-side honor** : seul Vertex AI applique le chunking côté serveur. Les autres providers (`openai`, `bedrock`, `s3_vectors`) appliquent leur propre stratégie interne — `chunking_strategy` peut être ignoré ou utilisé comme hint selon le provider. Vérifier dans les logs du proxy.

Pour OpenAI vector stores, le chunking est géré par OpenAI (par défaut `chunk_size=800` côté OpenAI). Pour contrôler finement, sortir de `/rag/ingest` et utiliser `/v1/embeddings` + insertion manuelle.

## Auto-provisioning détaillé

### Bedrock (`vector_store_id` omis)

LiteLLM crée :

1. **S3 bucket** pour stocker les documents source (`s3_prefix: "data/"` par défaut)
2. **OpenSearch Serverless collection** (vector engine)
3. **IAM role** avec permissions Bedrock + S3 + OpenSearch
4. **Bedrock Knowledge Base** liée à la collection
5. **Data Source** (S3 → KB)

Override possible : `s3_bucket`, `s3_prefix`, `embedding_model` (`amazon.titan-embed-text-v2:0` par défaut), `aws_region_name`.

### S3 Vectors (`index_name` omis)

LiteLLM crée :

1. **S3 vector bucket** (si absent)
2. **Index** avec dimension auto-détectée depuis `embedding.model`

Auto-detection : un appel test `/v1/embeddings` est fait pour mesurer la dimension. Marche avec n'importe quel modèle LiteLLM (OpenAI 1536D, Cohere 1024D, `qwen3-embedding` 1024D, etc.).

`non_filterable_metadata_keys` (default `["source_text"]`) : clés exclues du filtrage pour économiser l'index.

## Pipeline complet — exemple end-to-end

```python
# 1. Ingest
ingest_resp = requests.post(
    "http://127.0.0.1:8092/v1/rag/ingest",
    headers={"Authorization": f"Bearer {master}"},
    json={
        "file": {"filename": "guide.md", "content": b64, "content_type": "text/markdown"},
        "ingest_options": {"vector_store": {"custom_llm_provider": "openai"}},
    },
).json()

vs_id = ingest_resp["vector_store_id"]   # "vs_..."

# 2a. Search direct (no LLM generation)
search_resp = requests.post(
    f"http://127.0.0.1:8092/v1/vector_stores/{vs_id}/search",
    headers={"Authorization": f"Bearer {master}"},
    json={"query": "how do I configure fallbacks?", "max_num_results": 5},
).json()

# 2b. RAG query (search + LLM completion)
rag_resp = requests.post(
    "http://127.0.0.1:8092/v1/rag/query",
    headers={"Authorization": f"Bearer {master}"},
    json={
        "model": "gpt-5.5",
        "messages": [{"role": "user", "content": "How do I configure fallbacks?"}],
        "retrieval_config": {
            "vector_store_id": vs_id,
            "custom_llm_provider": "openai",
            "top_k": 5,
        },
    },
).json()
```

## Anti-patterns

1. **Oublier `wait_for_ingestion: true` sur Bedrock** → `status: "pending"` retourné, query immédiat retourne 0 résultats (indexing pas terminé).
2. **`chunking_strategy` sur OpenAI/Bedrock en attendant un découpage exact** → ignoré ou hint seulement. Pour contrôle fin, faire le chunking côté client + `/v1/embeddings` + insertion manuelle.
3. **Vertex AI sans corpus pré-créé** → 404. Le provider n'auto-crée pas, créer corpus + GCS bucket avant.
4. **Hardcoder la master key** dans un script → utiliser Keychain (`security find-generic-password`).
5. **Ingérer un PDF >10MB en `file` base64** → payload énorme + risque timeout. Utiliser `file_url`.
6. **Confondre `vector_store_id` (OpenAI `vs_*`) avec Bedrock KB id** → format différent, pas interchangeable. Toujours coupler `vector_store_id` avec son `custom_llm_provider`.
7. **Croire que `s3_vectors` + embedding local = souveraineté complète** → l'index est sur AWS S3 (cloud US). Pour Loi 25 full, voir `apple-data-indexer` (pgvector local).
8. **Re-ingérer le même fichier sans `file_id`** → duplication de chunks dans l'index. Réutiliser le `file_id` retourné.

## Troubleshooting

| Symptôme                                  | Cause probable                                | Fix                                                                                    |
| ----------------------------------------- | --------------------------------------------- | -------------------------------------------------------------------------------------- |
| `404 Not Found` sur `/v1/rag/ingest`      | Endpoint pas activé sur la version de LiteLLM | Vérifier version proxy ≥ celle qui ship `/rag/ingest` (cf. release notes upstream)     |
| `400 file required`                       | Aucun de `file`/`file_url`/`file_id` fourni   | Fournir exactement un des trois                                                        |
| `400 base64 decode error`                 | Padding manquant ou caractères invalides      | Utiliser `base64 -i file` (macOS) ou `base64.b64encode(bytes).decode()` (Python)       |
| `500 IAM permission denied` (Bedrock)     | Role créé sans permissions OpenSearch         | Re-tester après ~30s (propagation IAM) ou créer role manuel + passer `vector_store_id` |
| `dimension mismatch` (S3 Vectors)         | Index existant avec autre dimension           | Drop index ou changer `index_name`                                                     |
| Vertex AI `RagCorpus not found`           | `vector_store_id` mal formaté                 | Format complet : `projects/XXX/locations/us-central1/ragCorpora/YYY`                   |
| `status: "pending"` puis search vide      | Pas attendu l'indexing                        | `wait_for_ingestion: true` + `ingestion_timeout: 600`                                  |
| Cost tracking absent                      | Embedding model retourne pas d'usage info     | Configurer `model_info.input_cost_per_token` manuellement                              |
| Backend `qwen3-embedding` timeout (cas B) | MLX DOWN                                      | `aictl start qwen3-embedding`                                                          |

## Cross-references

| Skill                                 | Quand consulter                                                    |
| ------------------------------------- | ------------------------------------------------------------------ |
| `litellm-config-yaml`                 | Référence complète config proxy                                    |
| `litellm-providers-models`            | Liste exhaustive embedding models par provider                     |
| `litellm-logging-metrics`             | Trace Langfuse/OTel pour `/rag/ingest`                             |
| `litellm-budgets-spend`               | Cost tracking embedding + storage                                  |
| `litellm-guardrails-policies`         | PII masking sur le contenu ingéré (Loi 25)                         |
| `litellm-authentication`              | Virtual keys pour limiter accès au RAG par tenant                  |
| `intellisoins-mlx:apple-data-indexer` | Alternative pgvector local (souveraineté complète)                 |
| `intellisoins-mlx:vectordb`           | Concepts généraux vector DB (pgvector, Pinecone, Chroma, Weaviate) |
| `intellisoins-postgresml:pgml-embed`  | Embeddings in-DB Postgres17 (alternative à `/rag/ingest`)          |

Rules :

- `~/.claude/rules/local-ai-stack.md` — proxy port 8092, Keychain, MLX DOWN par défaut
- `~/.claude/rules/postgresml-usage.md` — RAG full-local Postgres17 + pgml.embed + pgml.rank
- `~/ai-servers/litellm-proxy/config.yaml:193-203` — `qwen3-embedding` + `bge-reranker-v2-m3`

Memory :

- `topic_data_residency_canada_llm.md` — souveraineté Loi 25, aucun frontier en data-in-use Canada

## Endpoints connexes (hors scope de ce skill)

- `/v1/rag/query` — RAG end-to-end (search + completion LLM)
- `/v1/vector_stores/{id}/search` — search direct dans un vector store
- `/v1/vector_stores` — CRUD vector stores
- `/v1/files` — upload de fichiers réutilisables (`file_id`)
- `/v1/embeddings` — embedding standalone (sans ingestion)

À couvrir dans skills séparés si besoin (`litellm-rag-query`, `litellm-vector-stores`, `litellm-files`).
