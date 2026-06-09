---
paths:
  - "**/litellm/Dockerfile*"
  - "**/litellm-*/Dockerfile*"
  - "**/docker/litellm/**"
  - "**/docker-compose*litellm*"
  - "**/*litellm*entrypoint*"
---

# LiteLLM Proxy Setup

Deploy the LiteLLM Proxy as an OpenAI-compatible gateway. Pattern: Docker Compose + PostgreSQL + (optional) Redis + (optional) Prometheus. Port 4000 by default.

## Minimum files

```
litellm/
├── docker-compose.yml
├── .env                 # secrets (gitignored)
├── config.yaml          # model_list + router + general_settings
└── prometheus.yml       # if Prometheus enabled
```

## docker-compose.yml (starter)

```yaml
services:
  litellm:
    image: ghcr.io/berriai/litellm:main-stable
    ports:
      - "4000:4000"
    environment:
      LITELLM_MASTER_KEY: ${LITELLM_MASTER_KEY}
      LITELLM_SALT_KEY: ${LITELLM_SALT_KEY}
      DATABASE_URL: postgresql://llmproxy:${POSTGRES_PASSWORD}@db:5432/litellm
    volumes:
      - ./config.yaml:/app/config.yaml
    command: ["--config", "/app/config.yaml", "--port", "4000", "--num_workers", "8"]
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: llmproxy
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: litellm
    volumes:
      - litellm_pg:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "llmproxy"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  litellm_pg:
```

For the official compose (with optional Prometheus): `curl -O https://raw.githubusercontent.com/BerriAI/litellm/main/docker-compose.yml`

## .env required vars

```bash
LITELLM_MASTER_KEY=sk-prod-master-$(openssl rand -hex 16)
LITELLM_SALT_KEY=sk-salt-$(openssl rand -hex 16)   # CANNOT be changed after first model stored
POSTGRES_PASSWORD=$(openssl rand -hex 24)

# Provider creds (referenced in config.yaml via os.environ/VAR_NAME)
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
VOYAGE_API_KEY=...
```

**Critical**: `LITELLM_SALT_KEY` encrypts stored provider API keys. Changing it after models are added renders existing key-refs undecryptable.

## Minimal config.yaml

```yaml
model_list:
  - model_name: claude-sonnet
    litellm_params:
      model: anthropic/claude-sonnet-4-6
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: gpt-4o
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  database_url: os.environ/DATABASE_URL
  database_connection_pool_limit: 15
```

Full reference: skill `litellm-config-yaml`.

## Start

```bash
docker compose up -d
docker compose logs -f litellm       # watch startup
curl http://localhost:4000/health    # liveness
```

## Test request

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

## Admin UI

URL: `http://localhost:4000/ui`
Login: master key (set in `LITELLM_MASTER_KEY`)

Features: virtual keys, teams, users, spend dashboards, model config, rate limits.

## Lancement sans Docker (commande `litellm` server)

Pour démarrer le serveur en local sans Docker — distinct de la CLI client `litellm-proxy` documentée plus bas.

```bash
pip install 'litellm[proxy]'

# Single model
litellm --model openai/gpt-4o --port 4000

# With config
litellm --config config.yaml --port 4000 --num_workers 8

# Debug
litellm --config config.yaml --detailed_debug
```

## Endpoints (OpenAI-compatible + extensions)

| Endpoint                        | Purpose                    |
| ------------------------------- | -------------------------- |
| `POST /v1/chat/completions`     | Chat                       |
| `POST /v1/completions`          | Legacy completion          |
| `POST /v1/embeddings`           | Embeddings                 |
| `POST /v1/images/generations`   | Image gen                  |
| `POST /v1/audio/transcriptions` | STT                        |
| `POST /v1/audio/speech`         | TTS                        |
| `POST /v1/rerank`               | Reranking                  |
| `GET /v1/models`                | List models                |
| `GET /health`                   | Proxy liveness             |
| `GET /health/liveliness`        | Full health check          |
| `GET /health/readiness`         | Ready probe                |
| `GET /metrics`                  | Prometheus metrics         |
| `POST /key/generate`            | Create virtual key (admin) |
| `POST /user/new` / `/team/new`  | User/team mgmt (admin)     |
| `GET /spend/logs`               | Spend audit (admin)        |
| `GET /docs`                     | Swagger UI                 |

Full Swagger: `http://localhost:4000/docs` or [litellm-api.up.railway.app](https://litellm-api.up.railway.app/).

## CLI client `litellm-proxy` (management)

Outil ligne de commande pour **gérer** un proxy LiteLLM déjà running (list models, generate keys, create users, etc.) — distinct de la commande `litellm` (section précédente) qui **lance** le serveur.

### Installation

```bash
uv tool install 'litellm[proxy]'   # installe les deux exécutables: `litellm` (server) + `litellm-proxy` (client)
# Alternative: pip install 'litellm[proxy]'
```

### Variables d'env

```bash
export LITELLM_PROXY_URL=http://localhost:8092       # proxy local Michael (4000 par défaut LiteLLM)
export LITELLM_PROXY_API_KEY=sk-your-key             # master key ou virtual key
litellm-proxy models list                             # premier appel pour valider
```

### Commandes principales

| Domaine      | Exemple                                                                                                                                                           |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Models       | `litellm-proxy models add gpt-4 --param api_key=sk-123 --param max_tokens=2048`                                                                                   |
| Credentials  | `litellm-proxy credentials create azure-prod --info='{"custom_llm_provider":"azure"}' --values='{"api_key":"sk-123","api_base":"https://prod.azure.openai.com"}'` |
| Keys         | `litellm-proxy keys generate --models=gpt-4 --spend=100 --duration=24h --key-alias=my-key`                                                                        |
| Users        | `litellm-proxy users create --email=user@example.com --role=internal_user --max-budget=100.0`                                                                     |
| Chat         | `litellm-proxy chat completions gpt-4 -m "user:Hello, how are you?"`                                                                                              |
| HTTP request | `litellm-proxy http request POST /chat/completions --json '{"model":"gpt-4","messages":[{"role":"user","content":"Hello"}]}'`                                     |

Sous-commandes communes par domaine: `list`, `get`, `info`, `update`, `delete`. Flag `--debug` pour verbose output (server unreachable, auth failure, invalid params).

### SSO login (beta)

Démarrer le proxy avec `EXPERIMENTAL_UI_LOGIN=True litellm --config config.yaml`, puis :

```bash
litellm-proxy login   # ouvre un navigateur pour SSO, utile pour self-serve dev access
```

Génération/gestion de keys via API HTTP : skill `litellm-authentication`.

Source : docs.litellm.ai/docs/proxy/management_cli — scraped 2026-05-05.

## Workers (concurrency)

```bash
litellm --config config.yaml --num_workers 8
```

Rule of thumb: `num_workers = 2 * CPU cores` for I/O-bound LLM calls. Each worker is a separate Python process (uvicorn).

## Deployment targets

### Local Mac dev

- Colima or Docker Desktop
- Port 4000 exposed
- `.env` + `config.yaml` in project dir

### VPS OVH IntelliSoins (`llm.intellisoins.ca`)

- Réseau: `intellisoins-vps-network` (externe, partagé avec Traefik)
- Labels Traefik dans `docker-compose.yml`:
  ```yaml
  labels:
    - traefik.enable=true
    - traefik.http.routers.litellm.rule=Host(`llm.intellisoins.ca`)
    - traefik.http.routers.litellm.entrypoints=websecure
    - traefik.http.routers.litellm.tls.certresolver=letsencrypt
    - traefik.http.services.litellm.loadbalancer.server.port=4000
  ```
- PostgreSQL: soit container dédié (`db` ci-dessus), soit instance Postgres existante sur VPS (ajouter `litellm` DB + user)
- Backups DB: volume `litellm_pg` à inclure dans la rotation Restic existante
- Secrets: SOPS + age (voir skill `intellisoins-infrastructure:secrets-management`)
- Monitoring: Prometheus scrape `/metrics` → Grafana (skill `intellisoins-infrastructure:grafana-dashboards`)

### Kubernetes

Helm chart officiel: `oci://ghcr.io/berriai/litellm-helm`. Non couvert ici — voir docs.litellm.ai/docs/proxy/deploy.

## Upgrade path

```bash
docker compose pull
docker compose up -d
```

Migrations Prisma s'exécutent automatiquement au démarrage (via `DATABASE_URL`). Breaking changes tracking: [CHANGELOG](https://github.com/BerriAI/litellm/releases).

## Troubleshooting

| Symptôme                     | Cause probable                     | Fix                                                                        |
| ---------------------------- | ---------------------------------- | -------------------------------------------------------------------------- |
| Startup hang                 | DB non ready                       | Vérifier `depends_on.condition: service_healthy`                           |
| `Could not decrypt api_key`  | `LITELLM_SALT_KEY` changé          | Restaurer l'ancien salt_key ou re-créer les models                         |
| 401 sur requêtes             | Master key incorrect               | `echo $LITELLM_MASTER_KEY` vs header `Authorization: Bearer`               |
| 404 `/v1/chat/completions`   | `model_name` absent de config.yaml | Vérifier via `GET /v1/models`                                              |
| Spend = 0 pour modèle custom | Pricing absent                     | Set `input_cost_per_token` / `output_cost_per_token` dans `litellm_params` |

Plus: skill `litellm-advanced` section troubleshooting.

## Source

docs.litellm.ai/docs/proxy/docker_quick_start + deploy — scraped 2026-04-14.
