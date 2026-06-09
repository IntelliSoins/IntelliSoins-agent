---
paths:
  - "**/litellm*container*"
  - "**/code_interpreter*"
---

# LiteLLM `/v1/containers` — OpenAI Code Interpreter Containers

Endpoints OpenAI-compatibles pour gérer les **conteneurs Code Interpreter** : sessions d'exécution Python isolées (sandboxes) attachées à un assistant ou un thread. Permet d'exécuter du code, manipuler des fichiers, générer des graphiques dans un environnement éphémère côté OpenAI. Disponible côté SDK Python (`litellm.create_container`, etc.) et Proxy (`POST/GET/DELETE /v1/containers[/{id}]`).

> Pour l'usage **applicatif** de Code Interpreter (assistant qui exécute du code dans un container) : voir [Code Interpreter Guide](https://docs.litellm.ai/docs/guides/code_interpreter) upstream. Ce skill couvre uniquement la **gestion CRUD** des conteneurs.

## Matrice des features

| Feature              | Status | Notes                                                                                   |
| -------------------- | ------ | --------------------------------------------------------------------------------------- |
| Cost tracking        | ✓      | Coût attribué au virtual key qui crée le container                                      |
| Logging callbacks    | ✓      | Full request/response (Langfuse, OTel, Datadog — skill `litellm-logging-metrics`)       |
| Load balancing       | ✓      | Plusieurs deployments OpenAI (master key + projects)                                    |
| Proxy server support | ✓      | Intégration complète avec virtual keys + RBAC                                           |
| Spend management     | ✓      | Budget tracking + rate limiting par key/team/user (skill `litellm-budgets-spend`)       |
| Streaming            | ✗      | N/A pour CRUD (réponses synchrones uniques)                                             |
| Fallbacks            | ⚠      | N/A — OpenAI seul provider supporté (pas de chaîne de fallback inter-provider possible) |

## Provider supporté

| Provider | Statut | Notes                                 |
| -------- | ------ | ------------------------------------- |
| `openai` | ✓      | Support complet des 4 opérations CRUD |

> **Important** : OpenAI est actuellement le seul provider supporté. Anthropic, Bedrock, Vertex, Azure n'ont pas d'équivalent natif. Les autres providers seront ajoutés selon roadmap LiteLLM upstream.

## Stack locale Michael — prérequis

Le proxy local (`http://127.0.0.1:8092/v1`) **transmet** les requêtes `/v1/containers` directement à l'API OpenAI. Pas de backend MLX local possible (les conteneurs sont des sandboxes OpenAI managés).

Prérequis dans `~/ai-servers/litellm-proxy/.env` :

```bash
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxx
```

> Vérifier que `OPENAI_API_KEY` est bien chargée par le proxy (`docker compose logs litellm | grep -i openai`). Sans clé OpenAI valide → 401 sur toutes les routes `/v1/containers`.

Pas besoin de déclarer un `model_name` spécifique dans `config.yaml` pour les conteneurs : la résolution se fait via `custom_llm_provider=openai` (header / query / body / default).

## Quick Start

### SDK Python — sync

```python
import litellm
import os

os.environ["OPENAI_API_KEY"] = "sk-proj-xxxx"

container = litellm.create_container(
    name="My Code Interpreter Container",
    custom_llm_provider="openai",
    expires_after={
        "anchor": "last_active_at",
        "minutes": 20,
    },
)

print(f"Container ID: {container.id}")          # cntr_xxxxxxxxxxxx...
print(f"Container Name: {container.name}")      # My Code Interpreter Container
print(f"Status: {container.status}")            # active
print(f"Created at: {container.created_at}")    # 1234567890 (epoch)
```

### SDK Python — async

```python
from litellm import acreate_container

container = await acreate_container(
    name="My Code Interpreter Container",
    custom_llm_provider="openai",
    expires_after={"anchor": "last_active_at", "minutes": 20},
)
```

Toutes les opérations exposent leur variante async :

| Sync                         | Async                         |
| ---------------------------- | ----------------------------- |
| `litellm.create_container`   | `litellm.acreate_container`   |
| `litellm.list_containers`    | `litellm.alist_containers`    |
| `litellm.retrieve_container` | `litellm.aretrieve_container` |
| `litellm.delete_container`   | `litellm.adelete_container`   |

### Via Proxy local (recommandé — virtual keys + spend tracking)

Auth via Keychain (jamais hardcoder la master key). Cf. `local-ai-stack.md`.

```python
import subprocess
from openai import OpenAI

master = subprocess.check_output([
    "security", "find-generic-password",
    "-a", "michaelahern", "-s", "litellm-master-key", "-w",
]).decode().strip()

client = OpenAI(base_url="http://127.0.0.1:8092/v1", api_key=master)

container = client.containers.create(
    name="test-container",
    expires_after={"anchor": "last_active_at", "minutes": 20},
    extra_body={"custom_llm_provider": "openai"},
)

print(f"Container ID: {container.id}")
```

> Le `extra_body={"custom_llm_provider": "openai"}` n'est strictement requis que si tu veux forcer un provider non-default. Le default est déjà `openai`. Garde-le explicite si plusieurs providers seront supportés à terme.

### Curl (test rapide)

```bash
MASTER=$(security find-generic-password -a "$USER" -s litellm-master-key -w)

curl -X POST 'http://127.0.0.1:8092/v1/containers' \
  -H "Authorization: Bearer $MASTER" \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "My Container",
    "expires_after": {"anchor": "last_active_at", "minutes": 20}
  }'
```

## Résolution `custom_llm_provider` (priorité)

Le proxy résout le provider dans cet ordre (premier match gagne) :

1. **Header** : `-H "custom-llm-provider: openai"`
2. **Query param** : `?custom_llm_provider=openai`
3. **Body** : `{"custom_llm_provider": "openai", ...}`
4. **Default** : `"openai"` si rien n'est spécifié

Trois équivalents pour créer un container :

```bash
# Default (le plus simple)
curl -X POST 'http://127.0.0.1:8092/v1/containers' \
  -H "Authorization: Bearer $MASTER" \
  -H 'Content-Type: application/json' \
  -d '{"name": "My Container"}'

# Via header
curl -X POST 'http://127.0.0.1:8092/v1/containers' \
  -H "Authorization: Bearer $MASTER" \
  -H "custom-llm-provider: openai" \
  -H 'Content-Type: application/json' \
  -d '{"name": "My Container"}'

# Via query param
curl -X POST 'http://127.0.0.1:8092/v1/containers?custom_llm_provider=openai' \
  -H "Authorization: Bearer $MASTER" \
  -H 'Content-Type: application/json' \
  -d '{"name": "My Container"}'
```

## Workflow complet (CRUD)

### 1. Create

```python
container = client.containers.create(
    name="My Code Interpreter Session",
    expires_after={"anchor": "last_active_at", "minutes": 20},
    extra_body={"custom_llm_provider": "openai"},
)
container_id = container.id   # cntr_6901d28b3c8881908b702815828a5bde0380b3408aeae8c7
```

### 2. List

```python
containers = client.containers.list(
    limit=20,
    extra_body={"custom_llm_provider": "openai"},
)

for c in containers.data:
    print(f"  - {c.id}: {c.name} (Status: {c.status})")

# Pagination
if containers.has_more:
    next_page = client.containers.list(
        limit=20,
        after=containers.last_id,
        extra_body={"custom_llm_provider": "openai"},
    )
```

### 3. Retrieve

```python
retrieved = client.containers.retrieve(
    container_id=container_id,
    extra_body={"custom_llm_provider": "openai"},
)

print(f"Status: {retrieved.status}")              # active | expired | deleted
print(f"Last active: {retrieved.last_active_at}") # epoch — pivot pour expires_after.anchor
print(f"Expires at: {retrieved.expires_at}")      # epoch
```

### 4. Delete

```python
result = client.containers.delete(
    container_id=container_id,
    extra_body={"custom_llm_provider": "openai"},
)

print(f"Deleted: {result.deleted}")  # True
print(f"Container ID: {result.id}")  # cntr_xxxx
```

### Endpoints REST équivalents

| Opération | Méthode + Route                                         |
| --------- | ------------------------------------------------------- |
| Create    | `POST /v1/containers`                                   |
| List      | `GET /v1/containers?limit=20&order=desc&after=<cursor>` |
| Retrieve  | `GET /v1/containers/{container_id}`                     |
| Delete    | `DELETE /v1/containers/{container_id}`                  |

## Paramètres

### Create Container

| Paramètre               | Type    | Required | Description                                             |
| ----------------------- | ------- | -------- | ------------------------------------------------------- |
| `name`                  | string  | **Yes**  | Nom lisible du container                                |
| `expires_after`         | object  | No       | Settings d'expiration                                   |
| `expires_after.anchor`  | string  | No       | Pivot temporel (ex: `"last_active_at"`)                 |
| `expires_after.minutes` | integer | No       | Minutes d'inactivité avant expiration                   |
| `file_ids`              | array   | No       | Fichiers OpenAI pré-uploadés à attacher (ID `file-xxx`) |
| `custom_llm_provider`   | string  | No       | Provider (default `"openai"`)                           |

### List Containers

| Paramètre             | Type    | Required | Description                                          |
| --------------------- | ------- | -------- | ---------------------------------------------------- |
| `after`               | string  | No       | Cursor de pagination (utiliser `containers.last_id`) |
| `limit`               | integer | No       | 1-100, default 20                                    |
| `order`               | string  | No       | `"asc"` ou `"desc"` (default `"desc"`)               |
| `custom_llm_provider` | string  | No       | Provider (default `"openai"`)                        |

### Retrieve / Delete Container

| Paramètre             | Type   | Required | Description                   |
| --------------------- | ------ | -------- | ----------------------------- |
| `container_id`        | string | **Yes**  | ID `cntr_xxx`                 |
| `custom_llm_provider` | string | No       | Provider (default `"openai"`) |

## Response objects

### `ContainerObject` (create / retrieve)

```json
{
  "id": "cntr_6901d28b3c8881908b702815828a5bde0380b3408aeae8c7",
  "object": "container",
  "created_at": 1234567890,
  "name": "My Container",
  "status": "active",
  "last_active_at": 1234567890,
  "expires_at": 1234569090,
  "file_ids": []
}
```

### `ContainerListResponse` (list)

```json
{
  "object": "list",
  "data": [
    {
      "id": "cntr_xxx",
      "object": "container",
      "created_at": 1234567890,
      "name": "My Container",
      "status": "active"
    }
  ],
  "first_id": "cntr_xxx",
  "last_id": "cntr_yyy",
  "has_more": false
}
```

### `DeleteContainerResult` (delete)

```json
{
  "id": "cntr_xxx",
  "object": "container.deleted",
  "deleted": true
}
```

## Cost tracking & Spend management

Les opérations `/v1/containers` sont logguées comme tout autre call OpenAI :

- **Spend attribué** au virtual key de l'`Authorization: Bearer <key>` qui a fait la requête.
- **Coût brut** : voir tarification OpenAI Code Interpreter (par session × durée). LiteLLM n'invente pas de coût — il propage celui retourné par OpenAI.
- **Audit** : `GET /spend/logs?api_key=<vkey>` ou Admin UI → Spend Logs filtré par `route=/v1/containers`.
- **Budgets** : appliquer `max_budget` / `tpm_limit` / `rpm_limit` au virtual key qui crée les containers (skill `litellm-budgets-spend`).

Exemple de virtual key dédiée Code Interpreter :

```bash
curl -X POST 'http://127.0.0.1:8092/key/generate' \
  -H "Authorization: Bearer $MASTER" \
  -H 'Content-Type: application/json' \
  -d '{
    "key_alias": "code-interpreter-prod",
    "max_budget": 50.0,
    "budget_duration": "30d",
    "rpm_limit": 10,
    "metadata": {"use_case": "containers + code_interpreter"}
  }'
```

## Logging

Cf. skill `litellm-logging-metrics` pour la config complète. Les opérations CRUD `/v1/containers` apparaissent dans :

- **Langfuse** : trace `litellm-call` avec `metadata.endpoint = /v1/containers/...`
- **OTel** : span `litellm.create_container` (et variantes)
- **Prometheus** : compteur `litellm_total_requests{route="/v1/containers", method="POST"}`

Filtrage utile en SQL Langfuse :

```sql
SELECT id, name, metadata->>'endpoint' AS route, latency_ms
FROM traces
WHERE metadata->>'endpoint' LIKE '/v1/containers%'
ORDER BY created_at DESC LIMIT 50;
```

## Anti-patterns

1. **Hardcoder la master key** dans un script Python → utiliser Keychain (`security find-generic-password`).
2. **Oublier `name`** lors du create → 400 Bad Request (paramètre requis).
3. **Réutiliser un container après `expires_at`** → 404 ou 410. Toujours vérifier `retrieved.status == "active"` avant d'attacher à un assistant.
4. **Créer un container par requête utilisateur sans cleanup** → fuite de coût (chaque container actif consomme tant qu'il n'expire pas). Soit fixer un `expires_after.minutes` court (5-20), soit `delete_container` explicite en fin de workflow.
5. **Routing vers `/v1/containers` sans `OPENAI_API_KEY` valide** → 401. La clé doit être présente dans `~/ai-servers/litellm-proxy/.env` et chargée par le container Docker.
6. **Compter sur des fallbacks inter-provider** → impossible (OpenAI seul supporte cet endpoint). Pour la résilience, mettre plusieurs deployments OpenAI (master key différentes / orgs / projects).

## Troubleshooting

| Symptôme                                  | Cause probable                                        | Fix                                                                                  |
| ----------------------------------------- | ----------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `404 Not Found` sur `/v1/containers`      | Version LiteLLM trop ancienne                         | `pip install -U litellm` ou bump l'image Docker (>= v1.55+)                          |
| `401 Unauthorized` (côté upstream OpenAI) | `OPENAI_API_KEY` absente / invalide dans `.env` proxy | Vérifier `docker compose exec litellm env \| grep OPENAI`                            |
| `400 Bad Request` "name required"         | Body manquant `name`                                  | Ajouter `"name": "..."` dans le payload                                              |
| `404` sur retrieve / delete               | Container expiré (depasse `expires_after.minutes`)    | `list_containers()` pour voir les containers actifs                                  |
| Cost tracking absent dans Admin UI        | Provider ne retourne pas d'`usage` pour cet endpoint  | Vérifier les logs raw (`/spend/logs`) — le coût est dans `metadata.openai_call_cost` |
| Pagination saute des containers           | `order` mal aligné avec `after` cursor                | Garder `order=desc` et utiliser `last_id` du précédent batch comme `after`           |

## Cross-references

| Skill                      | Quand consulter                                                      |
| -------------------------- | -------------------------------------------------------------------- |
| `litellm-budgets-spend`    | Limiter le coût Code Interpreter par virtual key / team              |
| `litellm-authentication`   | Créer une virtual key dédiée + RBAC pour Code Interpreter            |
| `litellm-logging-metrics`  | Tracer les appels CRUD container (Langfuse, OTel, Prometheus)        |
| `litellm-config-yaml`      | Référence `general_settings`, `litellm_settings` (logging callbacks) |
| `litellm-proxy-setup`      | Démarrer le proxy local Docker + Admin UI                            |
| `litellm-providers-models` | Tracker l'ajout de nouveaux providers supportant containers          |

Rules :

- `~/.claude/rules/local-ai-stack.md` — proxy port 8092, Keychain master key, env Docker
- `~/ai-servers/litellm-proxy/.env` — `OPENAI_API_KEY` requise
- `~/ai-servers/litellm-proxy/config.yaml` — pas de `model_list` entry requise pour `/v1/containers`

## Endpoints connexes (hors scope de ce skill)

- **`/v1/containers/{container_id}/files`** — Container Files API (upload/list/delete fichiers dans un container) — voir [Container Files API](https://docs.litellm.ai/docs/container_files) upstream.
- **`/v1/responses` avec `tools=[{"type": "code_interpreter", "container": "cntr_xxx"}]`** — usage applicatif via Responses API (Code Interpreter Guide upstream).
- **`/v1/assistants` + `tool_resources.code_interpreter.container_ids=[...]`** — usage via Assistants API.

À couvrir dans des skills séparés si besoin (`litellm-container-files`, `litellm-responses-api`, `litellm-assistants-api`).
