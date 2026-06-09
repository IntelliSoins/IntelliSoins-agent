---
paths:
  - "**/litellm*.env*"
  - "**/secrets/litellm*"
  - "**/litellm*/auth*"
  - "**/virtual_keys*"
  - "**/jwt*litellm*"
---

# LiteLLM Authentication & Virtual Keys

Three-layer auth model: master key (admin) → teams/users (organization) → virtual keys (client-facing).

## Prerequisites

- PostgreSQL via `DATABASE_URL`
- `master_key` in `general_settings` or `LITELLM_MASTER_KEY` env (must start with `sk-`)
- `LITELLM_SALT_KEY` (encrypts stored provider credentials — **cannot be changed after first model**)

## References (advanced / enterprise topics)

Sections externalisées pour garder ce SKILL.md lean. Lire le fichier référencé quand le sujet est requis.

| Sujet                                                                 | Fichier                                 | Quand consulter                                                                                                             |
| --------------------------------------------------------------------- | --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| JWT → Virtual Key Mapping (Enterprise)                                | `references/jwt-virtual-key-mapping.md` | Map JWT clients (claim `client_id`/`azp`/`sub`) → virtual keys individuelles. Utile SSO + Claude Code per-developer limits. |
| Service Account keys                                                  | `references/service-accounts.md`        | Keys non-attachées à un user (production), `enforced_params`, persiste si user supprimé.                                    |
| RBAC complet (org_admin, team_admin Premium, team_member_permissions) | `references/rbac-complete.md`           | Setup organizations, team admins, granular team member permissions.                                                         |
| CLI Authentication                                                    | `references/cli-authentication.md`      | `litellm-proxy login`, `EXPERIMENTAL_UI_LOGIN`, `LITELLM_CLI_JWT_EXPIRATION_HOURS`.                                         |
| Custom Auth complet                                                   | `references/custom-auth.md`             | UserAPIKeyAuth fields complets, mode `auto` (custom + builtin), ProxyException.                                             |
| IP Address Filtering                                                  | `references/ip-filtering.md`            | `allowed_ips` whitelist (License feature).                                                                                  |
| Audit Logs                                                            | `references/audit-logs.md`              | `store_audit_logs`, S3 export, `LiteLLM-Changed-By` attribution.                                                            |
| Public / Private Routes                                               | `references/public-private-routes.md`   | `public_routes`, `admin_only_routes`, `allowed_routes`, wildcards `/path/*`.                                                |

Note: les fichiers `references/` restent dans le plugin (`~/.claude/plugins/intellisoins-plugins/intellisoins-litellm/skills/litellm-authentication/references/`).

## Master key

Admin-only. Used for:

- Generating virtual keys
- Creating users/teams
- Reading spend logs
- Updating config via admin API

Include as `Authorization: Bearer sk-master-...` on any `/user/*`, `/team/*`, `/key/*`, `/spend/*` endpoint.

## Generate virtual key

```bash
curl 'http://0.0.0.0:4000/key/generate' \
  --header 'Authorization: Bearer $LITELLM_MASTER_KEY' \
  --header 'Content-Type: application/json' \
  --data '{
    "models": ["claude-sonnet", "gpt-4o"],
    "max_budget": 100,
    "duration": "30d",
    "tpm_limit": 10000,
    "rpm_limit": 100,
    "max_parallel_requests": 5,
    "metadata": {"user": "ishaan@berri.ai", "env": "prod"},
    "team_id": "team-123",
    "user_id": "user-456"
  }'
```

Response: `{"key": "sk-abc123...", "key_name": "sk-...xyz", "expires": "..."}`.

### Key parameters

| Param                     | Type      | Description                                                                   |
| ------------------------- | --------- | ----------------------------------------------------------------------------- |
| `models`                  | list[str] | Allowed model names or access groups                                          |
| `user_id`                 | str       | Assign to user                                                                |
| `team_id`                 | str       | Assign to team (uses team budget/limits)                                      |
| `max_budget`              | float     | USD spend cap                                                                 |
| `budget_duration`         | str       | Reset window (`30s`, `30m`, `30h`, `30d`)                                     |
| `duration`                | str       | Key lifetime (`30d`, `24h`)                                                   |
| `tpm_limit` / `rpm_limit` | int       | Rate limits                                                                   |
| `max_parallel_requests`   | int       | Concurrent cap                                                                |
| `metadata`                | dict      | Custom tracking                                                               |
| `aliases`                 | dict      | Map requested model → actual (e.g., `{"gpt-3.5-turbo": "my-free-tier"}`)      |
| `allowed_cache_controls`  | list      | Restrict cache headers                                                        |
| `guardrails`              | list[str] | Apply guardrails (skill `litellm-guardrails-policies`)                        |
| `permissions`             | dict      | Fine-grained access                                                           |
| `model_max_budget`        | dict      | Per-model budget: `{"gpt-4o": {"budget_limit": "1.00", "time_period": "1d"}}` |

## Users

```bash
# Create user
curl 'http://localhost:4000/user/new' \
  -H 'Authorization: Bearer $LITELLM_MASTER_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "user_email": "krrish@berri.ai",
    "user_role": "internal_user",
    "max_budget": 50,
    "budget_duration": "30d"
  }'

# Get user info (spend, keys)
curl 'http://localhost:4000/user/info?user_id=<user_id>' \
  -H 'Authorization: Bearer $LITELLM_MASTER_KEY'
```

User roles: `proxy_admin`, `proxy_admin_viewer`, `internal_user`, `internal_user_viewer`, `customer` (end-user).

## Teams

```bash
# Create team
curl 'http://localhost:4000/team/new' \
  -H 'Authorization: Bearer $LITELLM_MASTER_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "team_alias": "pubmed-agents",
    "members_with_roles": [{"role": "admin", "user_id": "user-123"}],
    "max_budget": 500,
    "budget_duration": "30d",
    "rpm_limit": 1000,
    "tpm_limit": 100000,
    "models": ["claude-sonnet", "gpt-4o"]
  }'

# Add member
curl 'http://localhost:4000/team/member_add' \
  -H 'Authorization: Bearer $LITELLM_MASTER_KEY' \
  -d '{
    "team_id": "team-xyz",
    "max_budget_in_team": 100,
    "member": {"role": "user", "user_id": "ishaan"}
  }'
```

Team budget > personal user budget when key has `team_id`.

Pour RBAC complet (org_admin, team_admin Premium, team_member_permissions, endpoints /organization/\*) → voir `references/rbac-complete.md`. Pour service account keys (production, indépendantes d'un user) → voir `references/service-accounts.md`.

## Key management

```bash
# Info + spend
curl 'http://0.0.0.0:4000/key/info?key=<key>' -H 'Authorization: Bearer $MASTER'

# Update
curl -X POST 'http://localhost:4000/key/update' \
  -H 'Authorization: Bearer $MASTER' \
  -d '{"key": "<key>", "max_budget": 200}'

# Block / unblock
curl -X POST 'http://0.0.0.0:4000/key/block' -d '{"key": "..."}'
curl -X POST 'http://0.0.0.0:4000/key/unblock' -d '{"key": "..."}'

# Delete
curl -X POST 'http://0.0.0.0:4000/key/delete' -d '{"keys": ["sk-..."]}'
```

## Key rotation

### Manual (with grace period)

```bash
curl 'http://localhost:4000/key/sk-1234/regenerate' \
  -X POST \
  -H 'Authorization: Bearer $MASTER' \
  -d '{
    "max_budget": 100,
    "models": ["gpt-4o"],
    "grace_period": "48h"
  }'
```

### Scheduled auto-rotation (Enterprise)

```bash
export LITELLM_KEY_ROTATION_ENABLED=true
export LITELLM_KEY_ROTATION_CHECK_INTERVAL_SECONDS=3600
export LITELLM_KEY_ROTATION_GRACE_PERIOD=48h
```

Enable per-key:

```bash
curl 'http://0.0.0.0:4000/key/generate' \
  -d '{
    "models": ["gpt-4o"],
    "auto_rotate": true,
    "rotation_interval": "30d"
  }'
```

Valid intervals: `30s`, `30m`, `30h`, `30d`, `90d`.

## JWT / OIDC authentication

Accept tokens from an identity provider (Authentik, Keycloak, Auth0, Okta) instead of virtual keys.

```yaml
general_settings:
  enable_jwt_auth: true
  litellm_jwtauth:
    admin_jwt_scope: "litellm_proxy_admin"
    admin_allowed_routes: ["openai_routes", "info_routes"]
    public_key_ttl: 600
    user_id_jwt_field: "sub"
    team_ids_jwt_field: "groups"
    user_email_jwt_field: "email"
    role_mappings:
      - role: "admin"
        internal_role: "proxy_admin"
      - role: "developer"
        internal_role: "internal_user"
```

Required env: `JWT_PUBLIC_KEY_URL` (JWKS endpoint) or `JWT_PUBLIC_KEY` (PEM).

Client usage:

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer <jwt-token>" \
  -d '{"model": "gpt-4o", "messages": [...]}'
```

LiteLLM validates JWT, extracts claims, maps to user/team, enforces budgets.

Pour mapper JWT individuels → virtual keys (Enterprise, per-client budget/rate limits sans distribuer d'API keys) → voir `references/jwt-virtual-key-mapping.md`.

## Model access groups

Group models into access tiers:

```yaml
model_list:
  - model_name: claude-sonnet
    litellm_params:
      model: anthropic/claude-sonnet-4-6
    model_info:
      access_groups: ["premium"]

  - model_name: gpt-3.5-turbo
    litellm_params:
      model: openai/gpt-3.5-turbo
    model_info:
      access_groups: ["free-tier"]
```

Assign group to key:

```bash
curl 'http://localhost:4000/key/generate' \
  -d '{"models": ["free-tier"]}'     # user gets gpt-3.5-turbo only
```

## Custom key header

Avoid `Authorization: Bearer` conflict:

```yaml
general_settings:
  master_key: sk-1234
  litellm_key_header_name: "X-Litellm-Key"
```

Client:

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "X-Litellm-Key: Bearer sk-..." \
  -d '{...}'
```

## Custom auth plugin

```python
# custom_auth.py
from litellm.proxy._types import GenerateKeyRequest

async def custom_generate_key_fn(data: GenerateKeyRequest) -> dict:
    if data.team_id == "allowed-team":
        return {"decision": True}
    return {"decision": False, "message": "Team not authorized"}
```

```yaml
general_settings:
  custom_key_generate: custom_auth.custom_generate_key_fn
```

Pour la version complète (UserAPIKeyAuth fields, mode=auto, ProxyException) → voir `references/custom-auth.md`.

## Upperbound / default key params

```yaml
litellm_settings:
  upperbound_key_generate_params:
    max_budget: 100
    duration: "30d"
    tpm_limit: 10000
  default_key_generate_params:
    max_budget: 1.50
    models: ["gpt-3.5-turbo"]
    duration: null
```

Applies to all keys generated (constraints + defaults).

## Claude Code Max subscription via proxy

Route the **Claude Code CLI** through LiteLLM Proxy while authenticating with a **Max/Pro/Team/Enterprise subscription** (OAuth) instead of an `ANTHROPIC_API_KEY` billed per token. Two-layer auth pattern:

| Header                                | Purpose                                        | Handled by             |
| ------------------------------------- | ---------------------------------------------- | ---------------------- |
| `x-litellm-api-key: Bearer sk-...`    | Gateway access, virtual key budget/rate limits | LiteLLM                |
| `Authorization: Bearer <oauth_token>` | Max subscription auth                          | Forwarded to Anthropic |

### Proxy config

`forward_client_headers_to_llm_api: true` is the pivot setting — it forwards the user's OAuth bearer to Anthropic without LiteLLM stripping it.

```yaml
model_list:
  - model_name: anthropic-claude
    litellm_params:
      model: anthropic/claude-sonnet-4-6
  - model_name: claude-haiku
    litellm_params:
      model: anthropic/claude-haiku-4-5-20251001

general_settings:
  forward_client_headers_to_llm_api: true # forwards OAuth → Anthropic
litellm_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
```

Per-model header forwarding (whitelist) for finer control:

```yaml
model_group_settings:
  forward_client_headers_to_llm_api:
    - anthropic-claude
    - claude-haiku
```

Full `config.yaml` reference: skill `litellm-config-yaml`.

### Client side (Claude Code CLI)

```bash
export ANTHROPIC_BASE_URL=http://localhost:4000            # or llm.intellisoins.ca
export ANTHROPIC_MODEL="anthropic-claude"                  # must match model_name in config
export ANTHROPIC_CUSTOM_HEADERS="x-litellm-api-key: Bearer sk-virtual-key-..."
claude   # browser auth → "Claude account with subscription" → Max plan
```

### Direct call (verify wiring)

```bash
curl -X POST http://localhost:4000/v1/messages \
  -H "x-litellm-api-key: Bearer sk-virtual-key-..." \
  -H "Authorization: Bearer <oauth_token_from_max_plan>" \
  -H "Content-Type: application/json" \
  -d '{"model": "anthropic-claude", "max_tokens": 1024,
       "messages": [{"role": "user", "content": "Hello"}]}'
```

### Caveats

1. Claude subscription requise (Pro/Max/Team/Enterprise) — pas de token-based plan sans OAuth.
2. `forward_client_headers_to_llm_api` default `false` — activer explicitement.
3. `ANTHROPIC_MODEL` doit matcher `model_name` exact (case-sensitive).
4. Budget tracking virtual key requiert PostgreSQL `DATABASE_URL`. Déploiement: skill `litellm-proxy-setup`.

### IntelliSoins use case

Sur le gateway local `:8092` (cf. memory `project_litellm_gateway.md`): virtual key par dev avec `max_budget` mensuel (audit/cost attribution), `ANTHROPIC_BASE_URL=http://localhost:8092` + virtual key dans `ANTHROPIC_CUSTOM_HEADERS`. OAuth Max géré côté CLI (browser flow), LiteLLM le forward sans le stocker.

## Claude Code with non-Anthropic models

Use the **Claude Code CLI** with non-Anthropic providers (OpenAI, Gemini, Vertex AI, Azure, Bedrock, Together AI, Groq, local Ollama/vLLM/MLX) by routing through LiteLLM, which translates Anthropic Messages API ↔ provider format automatically.

### Proxy config (multi-provider)

```yaml
model_list:
  - model_name: gpt-4o
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY

  - model_name: gemini-3-flash
    litellm_params:
      model: gemini/gemini-3.0-flash-exp
      api_key: os.environ/GEMINI_API_KEY

  - model_name: vertex-gemini-3-flash
    litellm_params:
      model: vertex_ai/gemini-3-flash-preview
      vertex_credentials: os.environ/VERTEX_FILE_PATH
      vertex_project: "my-project"
      vertex_location: "us-east-1"

  - model_name: azure-gpt-4
    litellm_params:
      model: azure/gpt-4
      api_key: os.environ/AZURE_API_KEY
      api_base: os.environ/AZURE_API_BASE
      api_version: "2024-02-01"

  - model_name: ollama-llama3
    litellm_params:
      model: ollama/llama3:8b
      api_base: http://localhost:11434

  - model_name: vllm-local
    litellm_params:
      model: openai/qwen3-coder
      api_base: http://localhost:8000/v1
      api_key: "dummy"

litellm_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
```

Full provider prefix table (100+): skill `litellm-providers-models`.

### Client side (Claude Code CLI)

```bash
export ANTHROPIC_BASE_URL="http://localhost:4000"          # or llm.intellisoins.ca
export ANTHROPIC_AUTH_TOKEN="$LITELLM_MASTER_KEY"          # or virtual key sk-...
claude --model gpt-4o
claude --model gemini-3-flash
claude --model ollama-llama3
claude --model vllm-local
```

The `--model` flag must match a `model_name` from `model_list` exactly.

### Verify wiring (direct curl)

```bash
curl -X POST http://localhost:4000/v1/messages \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o", "max_tokens": 1000,
       "messages": [{"role": "user", "content": "What is the capital of France?"}]}'
```

### Translation mechanism

LiteLLM acts as bidirectional translator:

1. Receives Claude Code request in Anthropic Messages API format
2. Translates to target provider format (OpenAI Chat Completions, Gemini, Vertex, etc.)
3. Forwards to provider
4. Translates response back to Anthropic Messages API format
5. Returns to Claude Code

Tool calls, vision, streaming, structured output are translated when supported by both sides.

### Load balancing across providers

Combine multiple deployments under the same `model_name`:

```yaml
model_list:
  - model_name: gpt-4o
    litellm_params: { model: openai/gpt-4o, api_key: os.environ/OPENAI_API_KEY }
  - model_name: gpt-4o
    litellm_params:
      {
        model: azure/gpt-4o,
        api_key: os.environ/AZURE_API_KEY,
        api_base: os.environ/AZURE_API_BASE,
      }

router_settings:
  routing_strategy: simple-shuffle
  num_retries: 2
  timeout: 30
```

Full routing/fallback patterns: skill `litellm-routing-fallbacks`.

### Caveats

1. `--model` doit matcher `model_name` exact (case-sensitive). Aliases via virtual key `aliases`.
2. Provider feature parity non garantie (tool calls/vision/extended thinking). Use `drop_params: true` dans `litellm_settings` pour silencer les `BadRequestError`.
3. Local models (Ollama/vLLM/MLX): `api_key` placeholder string parfois requis même si le serveur ne valide pas.

### IntelliSoins use case

Sur le gateway local `:8092` (cf. memory `project_litellm_gateway.md`, 16 modèles déjà configurés):

- **Cost optimization** — router les tâches non-critiques vers gpt-4o-mini / Gemini Flash via Claude Code (Sonnet 4.6 conservé pour clinical-grade).
- **Loi 25 / data residency** — utiliser modèles locaux MLX (`omlx`, `vllm-mlx :8000`, `mlx-omni-server`) qui ne sortent pas du Mac M3 Max → `claude --model omlx-llama3-70b` reste 100% local.
- **Multi-provider fallback** — combiner Anthropic primary + OpenAI/Together AI fallback dans `router_settings` pour résilience.
- Virtual key par cas d'usage avec `models: ["clinical-grade"]` ou `["general-use"]` (voir Model access groups plus haut).

## IntelliSoins integration

- **Virtual keys par agent**: `pubmed-mcp-key`, `masterai-key`, `website-key`
- **Teams**: `team-medical` (Opus/Sonnet), `team-marketing` (Sonnet/Haiku)
- **JWT via Authentik**: integrer `authentik.intellisoins.ca` (voir skill `intellisoins-infrastructure:authentik-branding`)
- **Access groups**: `clinical-grade` (Opus, validation), `general-use` (Sonnet, Haiku)
- **Rotation**: 30d auto pour keys prod, grace 48h

## Source

docs.litellm.ai/docs/proxy/{virtual_keys,team_users,jwt_auth,service_accounts,custom_auth,virtual_keys#key-rotations,access_control,jwt_key_mapping,token_auth,token_cli,ip_address,audit_logs,public_endpoints} — scraped 2026-04-14 + 2026-05-06 enterprise refresh.
