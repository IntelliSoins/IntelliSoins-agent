---
paths:
  - "~/ai-servers/litellm-proxy/**"
  - "~/ai-servers/launchers/litellm-proxy.sh"
  - "**/litellm-config.yaml"
---

# Claude Code + LiteLLM — Local AI Gateway (Mac)

Mis à jour 2026-05-27. Cette rule décrit le proxy LiteLLM personnel de
Michael sur le host macOS, pas le LiteLLM Docker d'IntelliSoins.

## État actuel

LiteLLM local est maintenant un gateway DB-backed, pas une config minimale.
Ne pas revenir au pattern sans `master_key` / `general_settings`.

| Surface          | État                                                              |
| ---------------- | ----------------------------------------------------------------- |
| Proxy            | `http://127.0.0.1:8092`, OpenAI-compatible + Anthropic-compatible |
| Launcher         | `~/ai-servers/launchers/litellm-proxy.sh`                         |
| Config           | `~/ai-servers/litellm-proxy/config.yaml`                          |
| Registry aictl   | `~/ai-servers/servers.yaml`, entrée `litellm-proxy`               |
| Version vérifiée | LiteLLM `1.83.14` via `~/.venvs/litellm/bin/litellm --version`    |
| Auth             | `LITELLM_MASTER_KEY` et `LITELLM_SALT_KEY` lus depuis Keychain    |
| DB               | `postgresql://michaelahern@localhost:5432/litellm`                |
| Cache            | Redis local db `1`, namespace `litellm.caching`                   |
| Vector store     | sidecar `litellm-pgvector` sur `127.0.0.1:8093`                   |

Snapshot audit 2026-05-27: la DB contenait des virtual keys et spend logs,
mais `TeamTable=0`, `BudgetTable=0`, `MCPServerTable=0`. Re-vérifier avant
de conclure sur l'état courant.

## Architecture Claude Code

Deux chemins coexistent et doivent rester séparés:

| Mode                 | Base URL                | Auth                              | Usage                                                           |
| -------------------- | ----------------------- | --------------------------------- | --------------------------------------------------------------- |
| Claude Max natif     | unset                   | OAuth Claude Code                 | défaut global, usage Anthropic direct                           |
| LiteLLM projet-local | `http://127.0.0.1:8092` | master key ou virtual key LiteLLM | modèles OpenAI, Together, MLX, Ollama, aliases Claude via proxy |

Pour Claude Code sur ce Mac, garder Claude Max global par défaut. Activer
LiteLLM seulement par projet quand un checkout a besoin du proxy, du tracking,
des fallbacks ou des modèles non-Anthropic.

## Config actuelle à préserver

Le fichier `litellm-proxy/config.yaml` doit garder ces surfaces:

```yaml
general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  database_url: os.environ/DATABASE_URL
  salt_key: os.environ/LITELLM_SALT_KEY
  allow_client_side_credentials: false
  maximum_spend_logs_retention_period: "90d"
  disable_master_key_return: true

litellm_settings:
  drop_params: true
  enable_pre_call_checks: true
  cache: true
```

L'ancien conseil de retirer `master_key` et `general_settings` est périmé:
avec la DB locale `litellm`, ces champs sont requis pour l'auth gateway, les
virtual keys, les spend logs, l'Admin UI et la gouvernance.

## Modèles et aliases

La config expose plusieurs familles:

- OpenAI cloud: `gpt-5.5`, `gpt-4o` et aliases Claude Code `claude-openai-*`.
- Together cloud: `kimi-k2.6`, `qwen3-coder-480b`, `deepseek-*`, `glm-5.1`.
- Local via oMLX: `general-local`, `code-local`, `gemma4-12b`, `Qwen3.6-35B-A3B-4bit`.
- Embedding/rerank/audio: `qwen3-embedding`, `bge-reranker-v2-m3`,
  `whisper-stt`.
- Anthropic/OAuth forwarding: `anthropic-claude-*` and picker aliases.

Ne pas supposer qu'un modèle listé est UP. Les backends MLX peuvent être
DOWN par défaut ou on-demand. Vérifier avec `./aictl status`,
`./aictl health`, les ports locaux et les logs LiteLLM avant de diagnostiquer
un problème de modèle.

## Commandes opérationnelles

```bash
cd ~/ai-servers
./aictl status
./aictl health
./aictl restart litellm-proxy
./aictl logs litellm-proxy
security find-generic-password -a "$USER" -s litellm-master-key -w
```

Validation DB/cache:

```bash
pg_isready -h localhost -p 5432
psql -d litellm -Atc "select count(*) from \"LiteLLM_SpendLogs\";"
redis-cli -n 1 ping
```

Validation sidecar vector store:

```bash
lsof -nP -iTCP:8093 -sTCP:LISTEN
launchctl list | rg litellm-pgvector
```

## Sidecar pgvector

`litellm-pgvector` est un sidecar OpenAI-compatible Vector Stores API sur
`127.0.0.1:8093`, lancé par `launchers/litellm-pgvector.sh`. La config
LiteLLM le référence dans `vector_store_registry`; `servers.yaml` le déclare
comme service `vector_store`, donc `aictl status/health/install` doit couvrir
son LaunchAgent et son endpoint `/health`.

## Gouvernance gateway

Ce proxy est utilisable, mais les règles suivantes doivent guider les agents:

- Ne pas hardcoder de clés dans YAML, shell, `.env`, `settings.local.json` ou
  réponses conversationnelles.
- Utiliser des virtual keys par usage quand c'est possible: Claude Code,
  scripts, RAG, OpenClaw, tests.
- Ajouter budgets, limites RPM/TPM, allowlists de modèles et expirations
  avant de considérer le gateway "mature".
- Activer ou documenter les guardrails par route avant de prétendre qu'ils
  protègent les appels.
- Ajouter observabilité/callbacks/alertes avant d'appeler cela un gateway de
  production.

## Gotchas connus

- `allow_client_side_credentials: false` bloque les requêtes qui essaient de
  passer `api_key` / `api_base` côté client. Ajouter les providers côté serveur.
- Les erreurs 429 cloud, crédit Together épuisé, ou backend local DOWN doivent
  être traitées comme des problèmes de routage/capacité, pas comme une panne
  générique de Claude Code.
- Pour identifier le backend réel derrière un alias, inspecter
  `LiteLLM_SpendLogs.model` ou le header `x-litellm-model-id`; `model_group`
  reflète surtout l'alias demandé.
- Pour Claude Max natif, laisser `ANTHROPIC_BASE_URL`, `ANTHROPIC_API_KEY`,
  `CLAUDE_CODE_OAUTH_TOKEN` et `LITELLM_*` unset sauf bascule volontaire vers
  le chemin proxy/SDK.

## Cross-references

- aictl CLI et registre `~/ai-servers/`: skill `local-ai-servers`.
- Config principale: `~/ai-servers/litellm-proxy/config.yaml`.
- Launcher proxy: `~/ai-servers/launchers/litellm-proxy.sh`.
- Launcher vector store: `~/ai-servers/launchers/litellm-pgvector.sh`.
- Rule générale stack locale: `~/.claude/rules/local-ai-stack.md`.
