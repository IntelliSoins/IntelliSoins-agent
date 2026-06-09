---
paths:
  - "**/count_tokens*"
  - "**/litellm*tokens*"
  - "**/token_counter*"
---

# LiteLLM `/v1/messages/count_tokens` — Comptage de tokens cross-provider

Endpoint Anthropic-compatible pour **compter les tokens d'une requête avant de l'envoyer au modèle**. LiteLLM auto-route vers l'API native de comptage de chaque provider (Anthropic Token Counting, OpenAI Responses `/input_tokens`, Vertex `countTokens`, Bedrock `CountTokens`, Gemini `countTokens`). Réponse uniformisée : `{"input_tokens": <number>}`.

## Pourquoi ce skill ?

| Cas d'usage                                                              | Bénéfice                                            |
| ------------------------------------------------------------------------ | --------------------------------------------------- |
| Valider que le prompt rentre dans le context window avant `/v1/messages` | Évite les erreurs `context_length_exceeded` 400     |
| Estimer le coût d'une requête à l'avance                                 | Décision de fallback (Haiku vs Sonnet) selon taille |
| Pré-flight check avant un batch coûteux                                  | Réduit les appels inutiles                          |
| Tracker l'usage par end-user avant routing                               | Budget enforcement skill `litellm-budgets-spend`    |

## Matrice des features

| Feature           | Status | Notes                                                     |
| ----------------- | ------ | --------------------------------------------------------- |
| Cost tracking     | ✓      | Loggué via callbacks comme une requête normale            |
| End-user tracking | ✓      | Header `x-litellm-end-user-id` ou champ `user`            |
| Logging callbacks | ✓      | Langfuse, OTel, Datadog (skill `litellm-logging-metrics`) |
| Streaming         | ✗      | N/A pour count_tokens (réponse unique)                    |
| Guardrails        | ✗      | Pas de filtrage upstream (read-only sur input)            |

## Providers supportés (6)

| Provider           | API native utilisée                                                                                    | Notes                                                        |
| ------------------ | ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------ |
| Anthropic          | [Anthropic Token Counting API](https://docs.anthropic.com/en/docs/build-with-claude/token-counting)    | `claude-3-5-sonnet-20241022`, `claude-haiku-4-5`, etc.       |
| OpenAI             | [Responses API `/input_tokens`](https://platform.openai.com/docs/api-reference/responses/input-tokens) | Endpoint distinct de `chat/completions` (pas tiktoken local) |
| Vertex AI (Claude) | Vertex AI Partner Models Token Counter                                                                 | **Requiert** `vertex_count_tokens_location` ≠ `global`       |
| Bedrock (Claude)   | AWS Bedrock `CountTokens` API                                                                          | Inférence profile cross-region OK (`us.anthropic.*`)         |
| Gemini AI Studio   | `countTokens` API                                                                                      | `gemini-2.0-flash-exp`, etc.                                 |
| Vertex AI (Gemini) | Vertex AI `countTokens`                                                                                | Même contrainte `vertex_count_tokens_location`               |

## Quick Start

### 1. Démarrer le proxy

```bash
litellm --config /path/to/config.yaml
# RUNNING on http://0.0.0.0:4000
```

### 2. Compter les tokens (curl)

```bash
curl -X POST "http://localhost:4000/v1/messages/count_tokens" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-1234" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "messages": [
      {"role": "user", "content": "Hello, how are you?"}
    ]
  }'
```

**Réponse** :

```json
{ "input_tokens": 14 }
```

### 3. Compter les tokens (Python httpx)

```python
import httpx

response = httpx.post(
    "http://localhost:4000/v1/messages/count_tokens",
    headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer sk-1234",
    },
    json={
        "model": "claude-3-5-sonnet-20241022",
        "messages": [
            {"role": "user", "content": "Hello, how are you?"}
        ],
    },
)
print(response.json())   # {"input_tokens": 14}
```

> Note : pas de wrapper SDK Python LiteLLM dédié pour cet endpoint — l'usage canonique est HTTP direct (httpx, requests, fetch). Pour Anthropic SDK natif pointé sur le proxy, voir skill `litellm-anthropic-messages-api` (`base_url=` + `client.messages.count_tokens(...)`).

## Configuration `config.yaml`

```yaml
model_list:
  - model_name: claude-3-5-sonnet
    litellm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: claude-vertex
    litellm_params:
      model: vertex_ai/claude-3-5-sonnet-v2@20241022
      vertex_project: my-project
      vertex_location: us-east5
      vertex_count_tokens_location: us-east5 # CRITIQUE — voir note ci-dessous

  - model_name: claude-bedrock
    litellm_params:
      model: bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0
      aws_region_name: us-west-2
```

> **Vertex AI gotcha** : si `vertex_location: global` est utilisé pour `/v1/messages` (load balancing GCP), `countTokens` n'est **pas** disponible sur cette location. Override avec `vertex_count_tokens_location: us-east5` (ou autre région régionale) sinon `404 Not Found` côté Vertex. Vérifié dans la doc LiteLLM upstream.

## Format requête / réponse

### Requête

| Paramètre  | Type   | Requis | Description                             |
| ---------- | ------ | ------ | --------------------------------------- |
| `model`    | string | ✓      | Le modèle à utiliser pour le comptage   |
| `messages` | array  | ✓      | Tableau de messages au format Anthropic |

```json
{
  "model": "claude-3-5-sonnet-20241022",
  "messages": [
    { "role": "user", "content": "Hello!" },
    { "role": "assistant", "content": "Hi there!" },
    { "role": "user", "content": "How are you?" }
  ]
}
```

### Réponse

```json
{ "input_tokens": <number> }
```

| Champ          | Type    | Description                                 |
| -------------- | ------- | ------------------------------------------- |
| `input_tokens` | integer | Nombre de tokens dans les messages d'entrée |

## Exemples

### Avec system message

```bash
curl -X POST "http://localhost:4000/v1/messages/count_tokens" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-1234" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "messages": [
      {"role": "user", "content": "You are a helpful assistant. Please help me write a haiku about programming."}
    ]
  }'
```

### Conversation multi-tour

```bash
curl -X POST "http://localhost:4000/v1/messages/count_tokens" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-1234" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "messages": [
      {"role": "user", "content": "What is the capital of France?"},
      {"role": "assistant", "content": "The capital of France is Paris."},
      {"role": "user", "content": "What is its population?"}
    ]
  }'
```

### Vertex Claude

```bash
curl -X POST "http://localhost:4000/v1/messages/count_tokens" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-1234" \
  -d '{
    "model": "claude-vertex",
    "messages": [{"role": "user", "content": "Hello, world!"}]
  }'
```

### Bedrock Claude

```bash
curl -X POST "http://localhost:4000/v1/messages/count_tokens" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-1234" \
  -d '{
    "model": "claude-bedrock",
    "messages": [{"role": "user", "content": "Hello, world!"}]
  }'
```

## `/v1/messages/count_tokens` vs `/anthropic/v1/messages/count_tokens`

LiteLLM expose **deux** routes pour compter les tokens. Choisir selon le besoin.

| Endpoint                            | Route LiteLLM                              | Use case                                                                                                                                                        |
| ----------------------------------- | ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Anthropic-compatible cross-provider | `POST /v1/messages/count_tokens`           | Marche avec **tous** les providers supportés (Anthropic, Vertex, Bedrock, OpenAI Responses, Gemini). Auth `Authorization: Bearer sk-...` LiteLLM.               |
| Pass-through Anthropic natif        | `POST /anthropic/v1/messages/count_tokens` | Accès **direct** API Anthropic avec headers natifs (`x-api-key`, `anthropic-version`, `anthropic-beta: token-counting-2024-11-01`). Aucune translation LiteLLM. |

### Exemple pass-through (headers natifs)

```bash
curl --request POST \
    --url http://0.0.0.0:4000/anthropic/v1/messages/count_tokens \
    --header "x-api-key: $LITELLM_API_KEY" \
    --header "anthropic-version: 2023-06-01" \
    --header "anthropic-beta: token-counting-2024-11-01" \
    --header "content-type: application/json" \
    --data '{
        "model": "claude-3-5-sonnet-20241022",
        "messages": [{"role": "user", "content": "Hello, world"}]
    }'
```

> Voir skill `litellm-anthropic-messages-api` section pass-through pour la liste complète des routes `/anthropic/v1/*` et la sémantique du forward de headers.

## Stack locale Michael — proxy `:8092`

Le proxy local (`http://127.0.0.1:8092`, dual pattern A/B — voir mémoire `project_litellm_gateway.md`) expose nativement `/v1/messages/count_tokens` quand au moins un modèle Anthropic-compatible est dans le `model_list`. Master key dans Keychain (clé `litellm-master-key`). Test rapide :

```bash
LITELLM_KEY=$(security find-generic-password -a michaelahern -s litellm-master-key -w)
curl -X POST "http://127.0.0.1:8092/v1/messages/count_tokens" \
  -H "Authorization: Bearer ${LITELLM_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"claude-haiku-4-5","messages":[{"role":"user","content":"ping"}]}'
```

Si le proxy renvoie `{"error":"model not found"}`, vérifier `~/ai-servers/litellm-proxy/config.yaml` que le `model_name` ciblé existe et que le provider supporte count_tokens (cf. matrice ci-dessus — pas tous les modèles configurés sur le proxy ne le supportent, ex. embeddings et rerank n'en ont pas).

## Anti-patterns / debugging

| Symptôme                                                    | Cause probable                                                                                    | Fix                                                                                                                    |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `404 Not Found` sur `/v1/messages/count_tokens` côté Vertex | `vertex_location: global` (count_tokens indisponible)                                             | Ajouter `vertex_count_tokens_location: us-east5` au `litellm_params`                                                   |
| `model not found` LiteLLM                                   | `model_name` absent du `model_list` ou provider sans count_tokens API                             | Vérifier matrice 6 providers ; tester d'abord avec un Anthropic direct                                                 |
| Coût compté 2x dans Langfuse / OTel                         | Implementation incorrecte côté client (count_tokens **+** completion en double)                   | Compter une fois pour décider, pas pour chaque request — utiliser `usage.input_tokens` de la réponse `/v1/messages`    |
| Timeout sur Bedrock count_tokens                            | Inference profile cross-region pas activé sur le compte AWS                                       | Activer le profile `us.anthropic.*` dans la console Bedrock ou utiliser un model ID régional (`us-west-2/anthropic.*`) |
| Estimation locale tiktoken ≠ count_tokens API Anthropic     | Les tokenizers locaux n'ont pas exactement la même tokenization que l'API Anthropic en production | Toujours utiliser l'endpoint pour les décisions de routing — tiktoken est une approximation                            |

## Cross-references

| Besoin                                                      | Skill                            |
| ----------------------------------------------------------- | -------------------------------- |
| `/v1/messages` (envoi de la requête après count)            | `litellm-anthropic-messages-api` |
| `claude-agent-sdk` agent loop via `ANTHROPIC_BASE_URL`      | `litellm-claude-agent-sdk`       |
| Configurer `model_list` avec `vertex_count_tokens_location` | `litellm-config-yaml`            |
| Vérifier qu'un provider supporte count_tokens               | `litellm-providers-models`       |
| Forcer un budget basé sur `input_tokens` estimé             | `litellm-budgets-spend`          |
| Logger les comptages dans Langfuse / OTel                   | `litellm-logging-metrics`        |
| Routing/fallback selon la taille estimée du prompt          | `litellm-routing-fallbacks`      |
| Cache sémantique pour éviter de re-compter                  | `litellm-caching`                |

## Source

- Doc upstream LiteLLM : <https://docs.litellm.ai/docs/anthropic_unified> (section count_tokens)
- Anthropic Token Counting : <https://docs.anthropic.com/en/docs/build-with-claude/token-counting>
- OpenAI Responses `/input_tokens` : <https://platform.openai.com/docs/api-reference/responses/input-tokens>
