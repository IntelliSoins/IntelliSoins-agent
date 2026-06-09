---
paths:
  - "**/litellm-pgvector/**"
  - "**/litellm*vector*"
  - "**/vector_store*"
  - "**/qdrant*"
  - "**/pgvector*"
---

# LiteLLM `/vector_stores/*` — Gestion CRUD + Search

Trois sous-endpoints OpenAI-compatibles pour gérer des vector stores indépendamment du pipeline `/rag/query` :

| Endpoint                              | Rôle                          | Providers                                                                                        | SDK                                                   |
| ------------------------------------- | ----------------------------- | ------------------------------------------------------------------------------------------------ | ----------------------------------------------------- |
| `POST /v1/vector_stores`              | Créer un store                | OpenAI, Azure AI (passthrough), RAGFlow, **pg_vector** (sidecar)                                 | `litellm.vector_stores.acreate`                       |
| `/v1/vector_stores/{id}/files` (CRUD) | Gérer les files dans un store | **OpenAI uniquement**                                                                            | `client.vector_stores.files.*` (SDK OpenAI via proxy) |
| `POST /v1/vector_stores/{id}/search`  | Recherche pure (sans LLM)     | OpenAI, Azure OpenAI, Bedrock, Vertex RAG, Azure AI, Milvus, Gemini, **pg_vector** (8 providers) | `litellm.vector_stores.asearch`                       |

> **Différence avec `/rag/query`** : `/rag/query` est un **pipeline tout-en-un** (search → rerank → completion). Les endpoints `/vector_stores/*` sont des **primitives** : tu peux les composer manuellement ou utiliser `/vector_stores/search` seul si tu n'as pas besoin de générer une réponse LLM. Cf. skill `litellm-rag-query`.

## Matrice des features (par opération)

| Feature                 | Create | Files CRUD                | Search                         |
| ----------------------- | ------ | ------------------------- | ------------------------------ |
| Cost tracking           | ✓      | ⚠ partiel (delete = 0)    | ✓                              |
| Logging callbacks       | ✓      | ✓ (full request/response) | ✓                              |
| End-user tracking       | ✓      | ✓                         | ✓                              |
| Streaming               | ✗      | ✓ (file content)          | ✗                              |
| Mock response (testing) | ✓      | ⚠ pas documenté           | ⚠ pas documenté                |
| Multi-query batch       | N/A    | N/A                       | ✓ (search avec `query: [...]`) |
| Guardrails              | ✗      | ✗                         | ⚠ sur la query uniquement      |

## Stack locale Michael — pg_vector configuré (depuis 2026-05-06)

Le proxy local (`http://127.0.0.1:8092/v1`) a `pg_vector` actif via le sidecar `BerriAI/litellm-pgvector` :

| Composant                  | État                                                  | Référence                                                       |
| -------------------------- | ----------------------------------------------------- | --------------------------------------------------------------- |
| Sidecar `litellm-pgvector` | ✓ port 8093 (uvicorn `main:app`)                      | `~/ai-servers/litellm-pgvector/`                                |
| LaunchAgent                | ✓ `com.ai-servers.litellm-pgvector`                   | `~/Library/LaunchAgents/com.ai-servers.litellm-pgvector.plist`  |
| Launcher                   | ✓ pattern aligné `embedding.sh`                       | `~/ai-servers/launchers/litellm-pgvector.sh`                    |
| DB Postgres17              | ✓ `litellm_pgvector` (port 5432)                      | pgvector 0.8.2, 2 tables Prisma (`embeddings`, `vector_stores`) |
| Embedding backend          | ✓ `qwen3-embedding` MLX local 1024D                   | port 8084 via LiteLLM proxy                                     |
| Keychain                   | ✓ `litellm-pgvector-api-key` (sidecar SERVER_API_KEY) | `security find-generic-password -s litellm-pgvector-api-key -w` |
| Config proxy               | ✓ `vector_store_registry` ligne 368-382               | `~/ai-servers/litellm-proxy/config.yaml`                        |
| Backups install            | ✓ 3 backups horodatés `2026-05-06 13:05-13:09`        | rollback procedure documentée                                   |

**Loi 25 ✓ end-to-end** (embedding local + storage local + LLM final = au choix).

Options provider (mises à jour) :

| Provider                        | Loi 25 ?                          | Coût           | Cas d'usage Michael                                             |
| ------------------------------- | --------------------------------- | -------------- | --------------------------------------------------------------- |
| **`pg_vector` (sidecar local)** | ✓ **100% local**                  | $0 (infra Mac) | **Prod IntelliSoins, PII patient Québec — recommandé**          |
| OpenAI Vector Stores            | ❌ data US                        | Premium        | Tests, prototypage rapide, docs publics (PubMed, Health Canada) |
| Azure OpenAI                    | ⚠ selon région choisie            | Premium        | Si déjà sur Azure                                               |
| Bedrock Knowledge Base          | ✓ avec `ca-central-1`             | $$             | Alternative cloud souveraine                                    |
| Vertex AI RAG Engine            | ✓ avec Montréal Assured Workloads | $$             | Si stack Google                                                 |
| Azure AI Search                 | ⚠ selon région                    | $$             | Hybrid search BM25+vector                                       |
| Milvus                          | ✓ self-hosted possible            | $ infra        | Si scaling au-delà de pgvector                                  |
| Gemini File Search              | ❌ data US (Gemini hosted)        | $              | Léger, métadonnées riches                                       |
| RAGFlow                         | ✓ self-hosted                     | $ infra        | Dataset management seul (pas de search)                         |

> Pour PII patients québécois : **`pg_vector` self-hosted** est l'option par défaut maintenant (zéro hop cloud). Bedrock `ca-central-1` en backup si besoin scaling. Cf. mémoire `topic_data_residency_canada_llm.md`.

---

## pg_vector — sidecar BerriAI/litellm-pgvector

### Architecture

```
┌─────────────┐         ┌─────────────────────────┐         ┌─────────────────┐
│  Client     │  HTTPS  │  LiteLLM Proxy (8092)   │  HTTP   │  Sidecar (8093) │
│ (curl/SDK)  ├────────▶│  pg_vector router       ├────────▶│ FastAPI         │
└─────────────┘         └────────────┬────────────┘         │ litellm-pgvector│
                                     │                       └────────┬────────┘
                                     │ embedding gen                  │
                                     ▼                                ▼
                          ┌──────────────────────┐         ┌─────────────────┐
                          │ qwen3-embedding 8084 │         │ Postgres17 5432 │
                          │ MLX 1024D local      │         │ pgvector 0.8.2  │
                          └──────────────────────┘         └─────────────────┘
```

Le sidecar est un service **OpenAI-compatible** qui :

1. Expose `/v1/vector_stores`, `/v1/vector_stores/{id}/embeddings`, `/v1/vector_stores/{id}/embeddings/batch`, `/v1/vector_stores/{id}/search`
2. Génère les embeddings en appelant LiteLLM proxy (`EMBEDDING__BASE_URL=http://127.0.0.1:8092`)
3. Stocke vectors + metadata + content dans Postgres17 + pgvector

LiteLLM 1.83.14 expose `pg_vector` comme `LlmProviders` valide via `litellm/llms/pg_vector/vector_stores/transformation.py` — wrapper qui hérite de `OpenAIVectorStoreConfig`.

### Configuration sidecar `.env`

`~/ai-servers/litellm-pgvector/.env` (chmod 600) :

```bash
DATABASE_URL=postgresql://michaelahern@localhost:5432/litellm_pgvector?schema=public
SERVER_API_KEY=<keychain: litellm-pgvector-api-key>
HOST=127.0.0.1
PORT=8093
EMBEDDING__MODEL=openai/qwen3-embedding   # ⚠️ préfixe `openai/` REQUIS (sinon BadRequestError côté embedding_service.py)
EMBEDDING__BASE_URL=http://127.0.0.1:8092
EMBEDDING__API_KEY=<keychain: litellm-master-key>
EMBEDDING__DIMENSIONS=1024                 # Qwen3 1024D, pas 1536D OpenAI
```

> ⚠️ **Caveat installation** : `EMBEDDING__MODEL=qwen3-embedding` (sans préfixe) provoque `BadRequestError: LLM Provider NOT provided`. Toujours utiliser `openai/qwen3-embedding` même si le modèle est local — le préfixe indique le format de l'API du backend (OpenAI-compatible), pas le hosting cloud.

### Configuration LiteLLM proxy `vector_store_registry`

`~/ai-servers/litellm-proxy/config.yaml` :

```yaml
vector_store_registry:
  - vector_store_name: pgvector-local-smoke # alias logique
    litellm_params:
      vector_store_id: 7cb6eb11-f576-4929-9a3c-c5e2acbb6778 # un vs réel pré-créé
      custom_llm_provider: pg_vector
      api_base: http://127.0.0.1:8093
      api_key: os.environ/PG_VECTOR_API_KEY
```

`PG_VECTOR_API_KEY` dans `~/ai-servers/litellm-proxy/.env` (mirror du Keychain `litellm-pgvector-api-key`).

> Le `vector_store_registry` lie un `vector_store_name` à un `vector_store_id` spécifique pour la query simplifiée. Mais tu peux aussi créer/utiliser n'importe quel `vs_id` à la volée via `POST /v1/vector_stores` (cf. workflow ci-dessous).

### Workflow complet pg_vector

```bash
MASTER=$(security find-generic-password -a "$USER" -s litellm-master-key -w)

# 1. Créer un nouveau vector store via le proxy
VS_ID=$(curl -s -X POST "http://127.0.0.1:8092/v1/vector_stores" \
  -H "Authorization: Bearer $MASTER" -H "Content-Type: application/json" \
  -d '{"name":"pharmacy-protocols","custom_llm_provider":"pg_vector"}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")

echo "Created: $VS_ID"

# 2. Embedder un document via le proxy (qwen3-embedding 1024D MLX local)
EMB=$(curl -s -X POST "http://127.0.0.1:8092/v1/embeddings" \
  -H "Authorization: Bearer $MASTER" -H "Content-Type: application/json" \
  -d '{"model":"qwen3-embedding","input":"Le tylenol est contre-indiqué en insuffisance hépatique sévère."}' \
  | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin)['data'][0]['embedding']))")

# 3. Insérer dans le sidecar (port 8093 direct car le standard OpenAI vector_stores n'a pas /embeddings/batch)
PGVK=$(security find-generic-password -a "$USER" -s litellm-pgvector-api-key -w)
curl -s -X POST "http://127.0.0.1:8093/v1/vector_stores/$VS_ID/embeddings" \
  -H "Authorization: Bearer $PGVK" -H "Content-Type: application/json" \
  -d "{
    \"content\": \"Le tylenol est contre-indiqué en insuffisance hépatique sévère.\",
    \"embedding\": $EMB,
    \"metadata\": {\"source\": \"pharmaco-quebec-2026\", \"category\": \"contre-indications\"}
  }"

# 4. Search via le proxy (route → pg_vector)
curl -s -X POST "http://127.0.0.1:8092/v1/vector_stores/$VS_ID/search" \
  -H "Authorization: Bearer $MASTER" -H "Content-Type: application/json" \
  -d '{"query":"Quels médicaments éviter avec un foie endommagé ?","custom_llm_provider":"pg_vector"}'
# → top-k chunks avec score >= 0.94 sur le bon doc (validé empiriquement)
```

### Endpoints disponibles vs limitations

| Opération                | Proxy LiteLLM (8092)                                                             | Sidecar direct (8093)                                                                                             | Note                                                                                     |
| ------------------------ | -------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Create store             | ✓ via `pg_vector`                                                                | ✓                                                                                                                 | Identique                                                                                |
| List stores              | ⚠ `/vector_store/list` retourne `data:[]` (cosmetic, registry server-side bound) | ⚠ `GET /v1/vector_stores` retourne 500 (bug upstream `last_active_at` str au lieu de datetime, cf. `main.py:187`) | Workaround : `psql -d litellm_pgvector -c "SELECT id, name FROM vector_stores;"`         |
| Search                   | ✓ via `pg_vector`                                                                | ✓                                                                                                                 | Identique                                                                                |
| Embed single             | ✗ pas exposé                                                                     | ✓ `POST /v1/vector_stores/{id}/embeddings`                                                                        | Payload doit inclure `embedding` pré-calculé OU laisser sidecar appeler proxy embeddings |
| Embed batch              | ✗ pas exposé                                                                     | ✓ `POST /v1/vector_stores/{id}/embeddings/batch`                                                                  | Idem                                                                                     |
| Files CRUD               | ✗ OpenAI only                                                                    | ✗ N/A                                                                                                             | Le sidecar utilise `embeddings` directement, pas de concept `files`                      |
| `/rag/query` (one-shot)  | ✗ **pas supporté pour pg_vector**                                                | N/A                                                                                                               | Manque `pg_vector_ingestion.py` upstream — composer manuellement                         |
| `/rag/ingest` (one-shot) | ✗ **pas supporté pour pg_vector**                                                | N/A                                                                                                               | Idem                                                                                     |

### Bug upstream `GET /v1/vector_stores` 500

```
'str' object has no attribute 'timestamp'
File "/Users/michaelahern/ai-servers/litellm-pgvector/main.py", line 187
```

Cause : `last_active_at` est sérialisé en str depuis Postgres mais le code appelle `.timestamp()` dessus. N'affecte PAS create/embed/search. Fix candidat (à pousser upstream BerriAI ou patch local) :

```python
# main.py:187
last_active_at = vs.last_active_at
if isinstance(last_active_at, str):
    from dateutil.parser import isoparse
    last_active_at = isoparse(last_active_at)
ts = int(last_active_at.timestamp()) if last_active_at else None
```

---

## 1. Créer un vector store

`POST /v1/vector_stores` — crée un store et y attache optionnellement des files déjà uploadés (via `/v1/files`).

### SDK Python — async

```python
import litellm

response = await litellm.vector_stores.acreate(
    name="My Document Store",
    file_ids=["file-abc123", "file-def456"],
    expires_after={
        "anchor": "last_active_at",
        "days": 7,
    },
    chunking_strategy={
        "type": "static",
        "static": {
            "max_chunk_size_tokens": 800,
            "chunk_overlap_tokens": 400,
        },
    },
    metadata={
        "project": "rag-system",
        "environment": "production",
    },
)
print(response)
# {"id": "vs_abc123", "object": "vector_store", "status": "completed", ...}
```

### SDK Python — sync

```python
import litellm
response = litellm.vector_stores.create(name="My Store", file_ids=["file-..."])
```

### SDK OpenAI via Proxy

```python
from openai import OpenAI
import subprocess

master = subprocess.check_output([
    "security", "find-generic-password",
    "-a", "michaelahern", "-s", "litellm-master-key", "-w"
]).decode().strip()

client = OpenAI(api_key=master, base_url="http://127.0.0.1:8092/v1")
vs = client.vector_stores.create(name="My Store", file_ids=["file-abc123"])
```

> Ancien SDK OpenAI : `client.beta.vector_stores.create(...)`. SDK ≥ 1.50 : namespace `beta` retiré, utiliser `client.vector_stores.create(...)` direct.

### curl via Proxy

```bash
MASTER=$(security find-generic-password -a "$USER" -s litellm-master-key -w)

curl -X POST 'http://127.0.0.1:8092/v1/vector_stores' \
  -H "Authorization: Bearer $MASTER" \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "My Document Store",
    "file_ids": ["file-abc123", "file-def456"],
    "chunking_strategy": {
      "type": "static",
      "static": {
        "max_chunk_size_tokens": 800,
        "chunk_overlap_tokens": 400
      }
    },
    "metadata": {"project": "rag-system"}
  }'
```

### Champs du request body

| Champ                                            | Type     | Description                                           |
| ------------------------------------------------ | -------- | ----------------------------------------------------- |
| `name`                                           | string   | Nom du store                                          |
| `file_ids`                                       | string[] | IDs de files déjà uploadés via `/v1/files`            |
| `expires_after.anchor`                           | string   | Seul `"last_active_at"` supporté                      |
| `expires_after.days`                             | integer  | TTL après dernière activité                           |
| `chunking_strategy.type`                         | string   | `"static"` ou auto si omis                            |
| `chunking_strategy.static.max_chunk_size_tokens` | integer  | 100-4096, défaut 800                                  |
| `chunking_strategy.static.chunk_overlap_tokens`  | integer  | défaut 400                                            |
| `metadata`                                       | object   | Max 16 paires KV ; clés ≤64 chars, valeurs ≤512 chars |

### Response

```json
{
  "id": "vs_abc123",
  "object": "vector_store",
  "created_at": 1699061776,
  "name": "My Document Store",
  "bytes": 139920,
  "file_counts": {
    "in_progress": 0,
    "completed": 2,
    "failed": 0,
    "cancelled": 0,
    "total": 2
  },
  "status": "completed",
  "expires_after": { "anchor": "last_active_at", "days": 7 },
  "expires_at": null,
  "last_active_at": 1699061776,
  "metadata": { "project": "rag-system" }
}
```

`status: "in_progress"` = files en cours de chunking/embedding ; attendre `completed` avant de query.

### Mock response (testing CI)

```python
mock = {
    "id": "vs_mock123",
    "object": "vector_store",
    "created_at": 1699061776,
    "name": "Mock Store",
    "bytes": 0,
    "file_counts": {"in_progress": 0, "completed": 0, "failed": 0, "cancelled": 0, "total": 0},
    "status": "completed",
}
response = await litellm.vector_stores.acreate(name="Test", mock_response=mock)
```

### RAGFlow — dataset management (search non supporté)

```python
# Configurer dans config.yaml :
# vector_store_registry:
#   - vector_store_name: ragflow-corpus
#     custom_llm_provider: ragflow
#     api_base: https://ragflow.intellisoins.local
#     api_key: os.environ/RAGFLOW_API_KEY

response = await litellm.vector_stores.acreate(
    name="Pharmacy Protocols",
    custom_llm_provider="ragflow",
)
# RAGFlow expose seulement create/list/delete des datasets — pas de search via /vector_stores/search.
# Pour query : utiliser l'API RAGFlow native ou un pipeline manuel.
```

---

## 2. Gérer les files dans un store

**OpenAI uniquement** (limitation upstream documentée). Bedrock/Vertex/Milvus/etc. gèrent leurs files via leurs APIs natives, pas via LiteLLM.

### Create vector store file

`POST /v1/vector_stores/{vector_store_id}/files`

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8092/v1", api_key=master)

vs_file = client.vector_stores.files.create(
    vector_store_id="vs_abc123",
    file_id="file-NDbEDJTfqVh7S4Ugi3CGYw",
    chunking_strategy={
        "type": "static",
        "static": {
            "max_chunk_size_tokens": 800,
            "chunk_overlap_tokens": 400,
        },
    },
)
```

> Le `file_id` doit déjà exister (uploadé via `POST /v1/files`). Les attributs `chunking_strategy` ici **overrident** ceux du vector store pour ce file spécifique — utile pour mixer chunks fins (FAQ courtes) et chunks longs (manuels) dans le même store.

### List vector store files

`GET /v1/vector_stores/{vector_store_id}/files`

```python
files = client.vector_stores.files.list(
    vector_store_id="vs_abc123",
    limit=50,
    filter="completed",   # in_progress | completed | failed | cancelled
    order="desc",
)
```

| Param              | Type    | Défaut | Description            |
| ------------------ | ------- | ------ | ---------------------- |
| `after` / `before` | string  | —      | Curseurs de pagination |
| `filter`           | string  | —      | Statut de processing   |
| `limit`            | integer | 20     | Range 1-100            |
| `order`            | string  | `desc` | `asc` ou `desc`        |

### Retrieve vector store file

`GET /v1/vector_stores/{vector_store_id}/files/{file_id}`

```python
vs_file = client.vector_stores.files.retrieve(
    vector_store_id="vs_abc123",
    file_id="file-abc123",
)
```

### Delete vector store file

`DELETE /v1/vector_stores/{vector_store_id}/files/{file_id}`

```python
client.vector_stores.files.delete(
    vector_store_id="vs_abc123",
    file_id="file-abc123",
)
```

> Détache le file du store mais **ne supprime pas l'objet `file-xxx`** lui-même. Pour supprimer l'objet : `client.files.delete(file_id="file-abc123")`.

### Retrieve file content (Proxy-only — chunks streaming)

`GET /v1/vector_stores/{vector_store_id}/files/{file_id}/content`

```bash
curl -X GET "http://127.0.0.1:8092/v1/vector_stores/vs_abc123/files/file-abc123/content" \
  -H "Authorization: Bearer $MASTER"
```

> Retourne les **chunks tels que stockés post-traitement** (utile pour debug : voir comment le chunking_strategy a découpé le doc). Pas exposé dans le SDK OpenAI Python — call HTTP direct.

### Update file attributes (Proxy-only)

`POST /v1/vector_stores/{vector_store_id}/files/{file_id}`

```bash
curl -X POST "http://127.0.0.1:8092/v1/vector_stores/vs_abc123/files/file-abc123" \
  -H "Authorization: Bearer $MASTER" \
  -H 'Content-Type: application/json' \
  -d '{
    "attributes": {
      "category": "support-faq",
      "language": "en"
    }
  }'
```

> Patch les **custom attributes** (utilisables comme `filters` dans `/vector_stores/search`). Pratique pour annoter post-ingestion sans ré-uploader.

---

## 3. Search vector store (sans LLM completion)

`POST /v1/vector_stores/{vector_store_id}/search` — recherche pure, retourne les chunks pertinents. **Use case** : tu veux le contexte sans la réponse LLM finale (pour l'injecter dans un prompt custom, pour scorer, pour debug).

### SDK Python — async

```python
import litellm

response = await litellm.vector_stores.asearch(
    vector_store_id="vs_abc123",
    query="What is the capital of France?",
    max_num_results=5,
    ranking_options={"score_threshold": 0.7},
    rewrite_query=True,
    filters={"file_ids": ["file-abc123", "file-def456"]},
)
```

### Multi-query batch

```python
response = await litellm.vector_stores.asearch(
    vector_store_id="vs_abc123",
    query=[
        "What is the capital of France?",
        "What is the population of Paris?",
    ],
    max_num_results=10,
)
```

> Une seule requête HTTP avec plusieurs queries → réponse contient les top-k pour chaque query. Utile pour "expansion de query" ou multi-aspect search.

### Paramètres

| Champ                             | Type               | Description                                                 |
| --------------------------------- | ------------------ | ----------------------------------------------------------- |
| `vector_store_id`                 | string             | Path param                                                  |
| `query`                           | string OR string[] | Single ou batch                                             |
| `filters`                         | object             | `{"file_ids": [...]}` OU metadata custom (Gemini, Azure AI) |
| `max_num_results`                 | integer            | Top-k                                                       |
| `ranking_options.score_threshold` | float              | 0.0-1.0, filtre les scores < threshold                      |
| `rewrite_query`                   | boolean            | LLM réécrit la query avant search (améliore recall)         |

### Providers — examples

#### OpenAI (défaut)

```python
response = await litellm.vector_stores.asearch(
    vector_store_id="vs_abc123",
    query="What is LiteLLM?",
    custom_llm_provider="openai",   # défaut
)
```

#### Bedrock Knowledge Base (Loi 25 friendly via `ca-central-1`)

```python
import litellm
response = await litellm.vector_stores.asearch(
    vector_store_id="ABCD1234EF",        # KB ID Bedrock
    query="Protocoles pharmacie?",
    custom_llm_provider="bedrock",
)
```

> Le `vector_store_id` est l'**ID de la Knowledge Base AWS**. Pour Loi 25 : configurer la KB en `ca-central-1` avec source S3 chiffrée.

#### Vertex AI RAG Engine

```python
response = await litellm.vector_stores.asearch(
    vector_store_id="your-corpus-id",
    query="What is LiteLLM?",
    custom_llm_provider="vertex_ai",
    max_num_results=5,
)
```

#### Azure AI Search (hybrid BM25+vector)

```python
import os
os.environ["AZURE_SEARCH_API_KEY"] = "..."

response = await litellm.vector_stores.asearch(
    vector_store_id="my-vector-index",
    query="What is the capital of France?",
    custom_llm_provider="azure_ai",
    azure_search_service_name="your-search-service",
    litellm_embedding_model="azure/text-embedding-3-large",
    litellm_embedding_config={
        "api_base": "your-embedding-endpoint",
        "api_key": "your-embedding-api-key",
    },
    api_key=os.getenv("AZURE_SEARCH_API_KEY"),
)
```

> Azure AI Search expose **hybrid search** (BM25 + vector) — utile quand tu veux à la fois match exact (codes médicaux DIN, CIM-10) et match sémantique.

#### Milvus (self-hosted — souveraineté totale)

```python
import os
os.environ["MILVUS_API_KEY"] = "..."
os.environ["MILVUS_API_BASE"] = "https://milvus.intellisoins.local"

response = await litellm.vector_stores.asearch(
    vector_store_id="my-collection-name",
    query="What is the capital of France?",
    custom_llm_provider="milvus",
    litellm_embedding_model="azure/text-embedding-3-large",
    litellm_embedding_config={
        "api_base": "your-embedding-endpoint",
        "api_key": "your-embedding-api-key",
    },
    milvus_text_field="book_intro",   # champ Milvus contenant le texte
    api_key=os.getenv("MILVUS_API_KEY"),
)
```

> Milvus self-hosted = **option souveraine pure** (data on-prem complète). Combiné avec un embedding model local MLX (`bge-large-en` via mlx-omni-server) → 100% local, conforme Loi 25 strict.

#### Gemini File Search

```python
import os
os.environ["GEMINI_API_KEY"] = "..."

response = await litellm.vector_stores.asearch(
    vector_store_id="fileSearchStores/your-store-id",
    query="What is the capital of France?",
    custom_llm_provider="gemini",
    max_num_results=5,
    filters={"author": "John Doe", "category": "documentation"},
)
```

> Format `vector_store_id` = `fileSearchStores/{id}` (préfixe required). Filters metadata supporté nativement (rare — la plupart des providers ne le supportent pas directement).

### curl via Proxy (provider-agnostic)

```bash
curl -X POST 'http://127.0.0.1:8092/v1/vector_stores/vs_abc123/search' \
  -H "Authorization: Bearer $MASTER" \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "What is the capital of France?",
    "filters": {"file_ids": ["file-abc123"]},
    "max_num_results": 5,
    "ranking_options": {"score_threshold": 0.7},
    "rewrite_query": true
  }'
```

---

## Vector store registry (config.yaml)

Pour utiliser des providers non-OpenAI, déclarer dans `vector_store_registry` :

```yaml
# ~/ai-servers/litellm-proxy/config.yaml

model_list:
  - model_name: gpt-4o
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY

vector_store_registry:
  - vector_store_name: pgvector-local
    litellm_params:
      vector_store_id: <vs_id pré-créé via POST /v1/vector_stores>
      custom_llm_provider: pg_vector
      api_base: http://127.0.0.1:8093
      api_key: os.environ/PG_VECTOR_API_KEY

  - vector_store_name: bedrock-pharmacy-kb
    litellm_params:
      vector_store_id: ABCD1234EF
      custom_llm_provider: bedrock
      aws_region_name: ca-central-1

  - vector_store_name: milvus-clinical-notes
    litellm_params:
      vector_store_id: my-collection
      custom_llm_provider: milvus
      api_base: https://milvus.intellisoins.local
      api_key: os.environ/MILVUS_API_KEY
      litellm_embedding_model: bge-large-en # déjà dans model_list

  - vector_store_name: ragflow-protocols
    litellm_params:
      custom_llm_provider: ragflow
      api_base: https://ragflow.intellisoins.local
      api_key: os.environ/RAGFLOW_API_KEY
```

> Cf. skill `litellm-config-yaml` pour la référence complète. Le `vector_store_registry` permet aussi d'utiliser ces stores avec `/rag/query` (cf. skill `litellm-rag-query`).

---

## Composer avec `/chat/completions` (RAG manuel)

Au lieu de `/rag/query` (rigide, 3 providers), composer manuellement :

```python
# 1. Search (7 providers possibles)
search = await litellm.vector_stores.asearch(
    vector_store_id="ABCD1234EF",
    query=user_question,
    custom_llm_provider="bedrock",
    max_num_results=10,
)

# 2. Rerank optionnel (skill litellm-rerank)
ranked = await litellm.arerank(
    model="bge-reranker-v2-m3",
    query=user_question,
    documents=[r["text"] for r in search["data"]],
    top_n=3,
)

# 3. Completion avec contexte
ctx = "\n\n".join([search["data"][r["index"]]["text"] for r in ranked.results])
response = await litellm.acompletion(
    model="claude-3-sonnet-bedrock",
    messages=[
        {"role": "system", "content": f"Context:\n{ctx}"},
        {"role": "user", "content": user_question},
    ],
)
```

> Plus de tokens (3 round-trips) mais 100% flexible : provider de search ≠ provider de rerank ≠ provider de completion. Cas d'usage IntelliSoins : Milvus self-hosted (search) + bge-reranker MLX (rerank) + Bedrock `ca-central-1` (LLM) = chaîne entièrement Loi 25 conforme.

### Pipeline pg_vector + MLX local (stack actuelle Michael, 100% Loi 25)

```python
import litellm

# 1. Search via pg_vector (sidecar 8093 → Postgres17 + qwen3-embedding 1024D)
search = await litellm.vector_stores.asearch(
    vector_store_id="<vs_id>",   # ex: 7cb6eb11-... (smoke) ou nouveau créé
    query=user_question,
    custom_llm_provider="pg_vector",
    api_base="http://127.0.0.1:8093",
    api_key=os.environ["PG_VECTOR_API_KEY"],
    max_num_results=10,
)

# 2. Rerank via bge-reranker-v2-m3 MLX local (port 8085)
ranked = await litellm.arerank(
    model="bge-reranker-v2-m3",
    query=user_question,
    documents=[r["content"] for r in search["data"]],
    top_n=3,
)

# 3. Completion via medgemma-27b MLX local OU gpt-5.5 OpenAI cloud
ctx = "\n\n".join([search["data"][r["index"]]["content"] for r in ranked.results])
response = await litellm.acompletion(
    model="medgemma-27b",   # ou gpt-5.5 si Loi 25 OK pour ce cas
    messages=[
        {"role": "system", "content": f"Context:\n{ctx}"},
        {"role": "user", "content": user_question},
    ],
)
```

**3 round-trips, tous via `http://127.0.0.1:8092` (proxy unifié)**, embedding+storage+rerank 100% on-prem. Le LLM final est le seul choix de conformité (medgemma local OU cloud selon le cas).

---

## Anti-patterns

1. **Confondre `vector_store_id` OpenAI (`vs_xxx`) et autres providers** : Bedrock = KB ID alphanumérique, Vertex = corpus ID, Gemini = `fileSearchStores/{id}`, Azure AI = nom d'index. Vérifier le format attendu par provider.
2. **Utiliser `/vector_stores/{id}/files` avec un store non-OpenAI** → 400 ou comportement non-déterministe. Limitation upstream.
3. **`max_chunk_size_tokens` hors range [100, 4096]** → 400 Bad Request. Recommandé : 400-800 pour QA, 1500-2000 pour summarization.
4. **`chunk_overlap_tokens` ≥ `max_chunk_size_tokens`** → chunks redondants à 100%, gaspille storage + budget embeddings. Garder overlap ≤ 50% du chunk size.
5. **Oublier que `delete file` ne supprime pas l'objet `file-xxx`** → orphelin storage, billed quand même. Faire `client.files.delete(file_id)` après detach.
6. **Hardcoder la master key** → utiliser Keychain (`security find-generic-password`).
7. **`metadata` > 16 paires KV ou clés > 64 chars** → 400. Limitation OpenAI explicite.
8. **`expires_after.anchor` autre que `last_active_at`** → ignoré ou rejeté. Seule valeur supportée actuellement.
9. **Multi-query sans comprendre la sémantique** : `query: ["q1", "q2"]` retourne top-k pour chaque query, pas le top-k de l'union. Si tu veux un seul ranking unifié, faire un seul call par query puis merger.
10. **`rewrite_query: true` en prod sans monitoring** : la réécriture LLM peut changer le sens — toujours logger l'original ET la version réécrite (Langfuse trace).
11. **Search sur Bedrock KB sans IAM `bedrock:Retrieve`** → 403 Forbidden. Vérifier le rôle.
12. **Search sur Milvus sans `milvus_text_field`** → retourne des objets sans le contenu textuel attendu. Toujours spécifier le field name.
13. **Sidecar `litellm-pgvector` : `EMBEDDING__MODEL` sans préfixe `openai/`** → `BadRequestError: LLM Provider NOT provided` côté `embedding_service.py`. Toujours `openai/qwen3-embedding`, jamais `qwen3-embedding` seul.
14. **Utiliser `/rag/query` ou `/rag/ingest` avec `custom_llm_provider: pg_vector`** → `pg_vector` n'a pas de fichier `pg_vector_ingestion.py` dans `litellm/rag/ingestion/`. Pour pgvector, composer manuellement (`asearch` + `arerank` + `acompletion`).
15. **`GET /v1/vector_stores` du sidecar** → 500 (bug upstream `last_active_at` str). Pas bloquant pour create/embed/search, mais pour lister utiliser `psql -d litellm_pgvector -c "SELECT id, name FROM vector_stores;"`.

## Troubleshooting

| Symptôme                                                                          | Cause probable                                                                   | Fix                                                                                                                                                  |
| --------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `404 Not Found` sur `/v1/vector_stores`                                           | Version proxy LiteLLM antérieure au support vector_stores                        | Mettre à jour le container : skill `litellm-proxy-setup`                                                                                             |
| `400 Bad Request` "vector store not found"                                        | ID incorrect OU mauvais `custom_llm_provider`                                    | Lister via `client.vector_stores.list()` ou API native du provider                                                                                   |
| Status `in_progress` indéfini après create                                        | File processing bloqué upstream                                                  | Poll `client.vector_stores.retrieve(id)` ; vérifier `file_counts.failed`                                                                             |
| `client.beta.vector_stores` AttributeError                                        | SDK OpenAI ≥ 1.50 a retiré `beta`                                                | Utiliser `client.vector_stores` direct                                                                                                               |
| `429 Rate limit` sur create avec beaucoup de files                                | OpenAI rate limit sur file processing                                            | Batcher par 20 files, attendre `completed` avant next batch                                                                                          |
| Search retourne `[]` même avec docs ingérés                                       | Embeddings non générés (status `in_progress`) OU query trop éloignée             | Vérifier `status: "completed"` ; baisser `score_threshold`                                                                                           |
| Search Milvus retourne `text: null`                                               | `milvus_text_field` non spécifié ou mauvais nom                                  | Vérifier le schema Milvus côté GUI/CLI puis spécifier le field                                                                                       |
| `403 Forbidden` Bedrock                                                           | IAM `bedrock:Retrieve` manquant                                                  | Ajouter au rôle IAM associé à la session                                                                                                             |
| `rewrite_query` change complètement le sens                                       | LLM hallucine la réécriture                                                      | Désactiver pour queries critiques OU logger les deux versions                                                                                        |
| File content endpoint retourne 404                                                | File pas encore processé                                                         | Attendre `vector_store_files.list(filter="completed")`                                                                                               |
| Cost tracking incomplet                                                           | Provider non-OpenAI ne retourne pas `usage` standardisé                          | Configurer manuellement via `model_info` (cf. skill `litellm-config-yaml`)                                                                           |
| Sidecar `litellm-pgvector` `BadRequestError: LLM Provider NOT provided` sur embed | `EMBEDDING__MODEL` sans préfixe (ex: `qwen3-embedding`)                          | Mettre `openai/qwen3-embedding` dans `~/ai-servers/litellm-pgvector/.env` puis `launchctl kickstart -k gui/$(id -u)/com.ai-servers.litellm-pgvector` |
| Sidecar `GET /v1/vector_stores` retourne 500                                      | Bug upstream `last_active_at` str → `.timestamp()` (cf. `main.py:187`)           | Workaround : `psql -d litellm_pgvector -c "SELECT id, name FROM vector_stores;"`. Fix : patch local ou PR upstream BerriAI                           |
| Proxy `GET /vector_store/list` retourne `data:[]`                                 | LiteLLM 1.83.14 ne propage pas le `vector_store_registry` via cet endpoint admin | Comportement attendu (registry server-side bound). Le routing fonctionne quand même via `vector_store_id` explicite                                  |
| Sidecar pg_vector : `psycopg.errors.UndefinedTable`                               | Migration Prisma pas appliquée                                                   | `cd ~/ai-servers/litellm-pgvector && .venv/bin/python -m prisma db push` puis restart sidecar                                                        |

## Cross-references

| Skill                                | Quand consulter                                                                                                  |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| `litellm-rag-query`                  | Pipeline tout-en-un (search + rerank + completion en un appel) — alternative haut-niveau à composer manuellement |
| `litellm-rag-ingest`                 | Ingestion document → vector store en un appel (`POST /v1/rag/ingest`) — pré-requis avant query/search            |
| `litellm-rerank`                     | Cross-encoder reranking entre `/vector_stores/search` et `/chat/completions`                                     |
| `litellm-config-yaml`                | Référence `vector_store_registry`, `model_list`, `general_settings`                                              |
| `litellm-providers-models`           | Détails des providers vector store (Bedrock régions, Vertex projects, Milvus auth)                               |
| `litellm-routing-fallbacks`          | Fallbacks entre providers de search (ex: Milvus DOWN → Bedrock)                                                  |
| `litellm-guardrails-policies`        | Presidio sur la query de search (Loi 25)                                                                         |
| `litellm-logging-metrics`            | Trace Langfuse / OTel pour vector_stores calls                                                                   |
| `litellm-proxy-setup`                | Mise à jour container si endpoints `/vector_stores/*` retournent 404                                             |
| `intellisoins-postgresml:postgresml` | Alternative SQL-native (pgml.embed + pgvector) — pas via LiteLLM mais self-hosted complet                        |
| `intellisoins-mlx:mlx-embeddings`    | Embeddings MLX locaux pour Milvus / pgvector                                                                     |

Rules :

- `~/.claude/rules/local-ai-stack.md` — proxy port 8092, Keychain
- Mémoire `topic_data_residency_canada_llm.md` — Loi 25 : Bedrock `ca-central-1`, Vertex Montréal, Milvus self-hosted, IBM watsonx CA
- Mémoire `project_litellm_gateway.md` — proxy local config
- `~/ai-servers/litellm-proxy/config.yaml` — actuellement **sans** `vector_store_registry` (à ajouter pour activer les providers non-OpenAI)

## Endpoints connexes (hors scope de ce skill)

- `POST /v1/files` — upload de fichiers brut (pré-requis avant `vector_stores.files.create`)
- `POST /v1/rag/ingest` — ingestion en un seul appel (file upload + vector store + chunking) — skill `litellm-rag-ingest`
- `POST /v1/rag/query` — pipeline RAG one-shot (search + rerank + LLM) — skill `litellm-rag-query`
- `POST /v1/rerank` — cross-encoder reranking — skill `litellm-rerank`
- `POST /v1/embeddings` — génération d'embeddings standalone (pré-requis pour Milvus/pgvector custom)
