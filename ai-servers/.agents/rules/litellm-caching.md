---
paths:
  - "**/litellm*cache*"
  - "**/litellm*redis*"
  - "**/semantic_cache*"
---

# LiteLLM Caching

Seven cache backends. Enabled globally via `litellm_settings.cache`, controlled per-request via `cache` body parameter.

## Backends

| Type              | Use case                    | Distributed |
| ----------------- | --------------------------- | ----------- |
| `local`           | In-memory (single-process)  | No          |
| `disk`            | File-based persistence      | No          |
| `redis`           | Hash-based, exact match     | Yes         |
| `redis-semantic`  | Vector similarity on Redis  | Yes         |
| `qdrant-semantic` | Vector similarity on Qdrant | Yes         |
| `s3`              | AWS S3 object storage       | Yes         |
| `gcs`             | Google Cloud Storage        | Yes         |

## Enable

```yaml
litellm_settings:
  cache: true
  cache_params:
    type: redis
    namespace: "litellm.caching"
    ttl: 600
```

## Redis

```yaml
litellm_settings:
  cache: true
  cache_params:
    type: redis
    namespace: "litellm.caching"
    ttl: 600
    max_connections: 100
```

Env:

```bash
REDIS_URL="redis://user:pass@host:port/0"
# OR individual:
REDIS_HOST=redis.example.com
REDIS_PORT=6379
REDIS_PASSWORD=secret
REDIS_SSL=true
```

### Redis Cluster

```yaml
cache_params:
  type: redis
  redis_startup_nodes: [{ "host": "127.0.0.1", "port": "7001" }]
```

### Redis Sentinel

```yaml
cache_params:
  type: redis
  service_name: "mymaster"
  sentinel_nodes: [["localhost", 26379]]
  sentinel_password: "password"
```

## Redis Semantic Cache

Matches requests by cosine similarity of embeddings — returns cache hit when similar prompt exists.

```yaml
litellm_settings:
  cache: true
  cache_params:
    type: redis-semantic
    similarity_threshold: 0.8 # 0-1, higher = stricter
    redis_semantic_cache_embedding_model: azure-embedding-model
```

Threshold guide:

- 0.95+: near-duplicate only
- 0.85-0.95: paraphrases
- 0.7-0.85: topic-similar (risky — may return wrong answer)

## Qdrant Semantic Cache

```yaml
litellm_settings:
  cache: true
  cache_params:
    type: qdrant-semantic
    qdrant_semantic_cache_embedding_model: openai-embedding
    qdrant_collection_name: test_collection
    similarity_threshold: 0.8
    qdrant_semantic_cache_vector_size: 1536
```

Env:

```bash
QDRANT_API_KEY=key
QDRANT_API_BASE=https://qdrant.example.com
```

## S3

```yaml
litellm_settings:
  cache: true
  cache_params:
    type: s3
    s3_bucket_name: cache-bucket-litellm
    s3_region_name: us-west-2
    s3_aws_access_key_id: os.environ/AWS_ACCESS_KEY_ID
    s3_aws_secret_access_key: os.environ/AWS_SECRET_ACCESS_KEY
```

## GCS

```yaml
litellm_settings:
  cache: true
  cache_params:
    type: gcs
    gcs_bucket_name: cache-bucket-litellm
    gcs_path_service_account: os.environ/GCS_PATH_SERVICE_ACCOUNT
    gcs_path: cache/
```

## Disk

```yaml
litellm_settings:
  cache: true
  cache_params:
    type: disk
    disk_cache_dir: /tmp/litellm-cache
```

## In-memory (local)

```yaml
litellm_settings:
  cache: true
  cache_params:
    type: local
```

Single-process only. Lost on restart.

## Per-request cache control

Pass `cache` object in request body.

### TTL

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer sk-..." \
  -d '{
    "model": "gpt-3.5-turbo",
    "cache": {"ttl": 300},
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

Python SDK:

```python
from openai import OpenAI
client = OpenAI(api_key="...", base_url="http://0.0.0.0:4000")
response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello"}],
    extra_body={"cache": {"ttl": 300}},
)
```

### Skip cache

```bash
-d '{"cache": {"no-cache": true}, "model": "...", "messages": [...]}'
```

### Don't store response

```bash
-d '{"cache": {"no-store": true}, ...}'
```

### Age validation

Only accept cache entries newer than N seconds:

```bash
-d '{"cache": {"s-maxage": 600}, ...}'
```

### Custom namespace

Isolate cache by use case:

```bash
-d '{"cache": {"namespace": "medical-rag"}, ...}'
```

## Restrict cached endpoints

```yaml
litellm_settings:
  cache: true
  cache_params:
    type: redis
    supported_call_types:
      - acompletion
      - aembedding
      - atranscription
# Options: completion, acompletion, embedding, aembedding, atranscription, transcription
```

Disable caching entirely for LLM calls (use only rate limiter):

```yaml
cache_params:
  supported_call_types: []
```

## Default-off (opt-in per request)

```yaml
cache_params:
  mode: default_off
```

Opt-in:

```bash
-d '{"cache": {"use-cache": true}, ...}'
```

## Cache management endpoints

### Health

```bash
curl http://0.0.0.0:4000/cache/ping -H "Authorization: Bearer sk-..."
```

Response:

```json
{
  "status": "healthy",
  "cache_type": "redis",
  "ping_response": true,
  "set_cache_response": "success"
}
```

### Delete keys

```bash
curl -X POST http://0.0.0.0:4000/cache/delete \
  -H "Authorization: Bearer sk-..." \
  -d '{"keys": ["586bf3f3c1bf5aecb55..."]}'
```

### Inspect cache key

Response header on cache hits:

```
x-litellm-cache-key: 586bf3f3c1bf5aecb...
```

## Provider-specific param caching

Include non-OpenAI params (e.g., Anthropic's `system`) in cache key:

```yaml
cache_params:
  type: redis
  enable_caching_on_provider_specific_optional_params: true
```

## User API key cache

Separate from response cache — caches user key lookups:

```yaml
general_settings:
  user_api_key_cache_ttl: 60 # seconds
```

## Cache hit economics

- Redis hit: ~5-15ms total latency
- Semantic Redis hit: ~50-80ms (embedding + similarity search)
- Qdrant semantic hit: ~30-60ms
- Cost savings: 100% of LLM call (no provider charge)

## IntelliSoins patterns

### RAG queries (PubMed)

```yaml
# semantic cache on medical queries — high paraphrase rate
cache_params:
  type: redis-semantic
  similarity_threshold: 0.92 # strict for clinical accuracy
  namespace: "pubmed-rag"
  ttl: 86400 # 24h
```

### Embeddings (document indexation)

```yaml
# exact cache — embedding input rarely changes
cache_params:
  type: redis
  ttl: 2592000 # 30d (embeddings are deterministic)
  supported_call_types: ["aembedding"]
```

### Tool calls

Cache with short TTL (tool responses may be time-sensitive):

```bash
-d '{"cache": {"ttl": 60}, ...}'
```

## Troubleshooting

| Problème                             | Cause                       | Fix                                                                 |
| ------------------------------------ | --------------------------- | ------------------------------------------------------------------- |
| `/cache/ping` retourne error         | Redis down                  | Vérifier `REDIS_HOST` + firewall                                    |
| Pas de cache hit                     | Clé change à chaque requête | Vérifier params (temperature, user, metadata) qui invalident la clé |
| Semantic cache trop de faux positifs | Threshold trop bas          | Augmenter `similarity_threshold` à 0.9+                             |
| Cache stale                          | TTL trop long               | Réduire `ttl` ou utiliser `s-maxage`                                |

## Source

docs.litellm.ai/docs/proxy/caching — scraped 2026-04-14.
