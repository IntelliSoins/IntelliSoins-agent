---
paths:
  - "**/litellm/**"
  - "**/litellm-*/**"
  - "**/*litellm*.md"
---

# LiteLLM Overview

LiteLLM unifies 100+ LLM providers (OpenAI, Anthropic, Bedrock, Azure, Vertex, Ollama, Voyage) behind a single OpenAI-compatible interface. Two deployment modes — pick based on use case.

## Two modes

| Mode                          | Use when                                                               | Package                                           |
| ----------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------- |
| **Python SDK**                | Single app, in-process calls, prototyping, notebooks                   | `pip install litellm`                             |
| **Proxy Server (AI Gateway)** | Multi-team, virtual keys, spend tracking, guardrails, centralized logs | Docker container / `pip install 'litellm[proxy]'` |

Both share the same config format and provider mappings. The Proxy is the SDK wrapped in a FastAPI server with PostgreSQL for state (keys, spend, teams).

## Architecture (Proxy mode)

```
Client (OpenAI SDK) ─► LiteLLM Proxy :4000 ─► Router ─► Provider API
                            │
                            ├─► PostgreSQL (keys, spend, teams, audit)
                            ├─► Redis (cache + multi-instance sync)
                            ├─► Callbacks (Langfuse, Prometheus, S3, Slack)
                            └─► Guardrails (Presidio, Bedrock, Lakera)
```

## Python SDK quickstart

```python
from litellm import completion
import os

os.environ["OPENAI_API_KEY"] = "sk-..."

response = completion(
    model="openai/gpt-4o",
    messages=[{"role": "user", "content": "Hello"}]
)
print(response.choices[0].message.content)
```

Async: `acompletion()`. Streaming: `stream=True`. Embeddings: `embedding()`.
Consistent output format across all providers — response schema matches OpenAI.

## Proxy quickstart

```bash
# One-line start (single model)
litellm --model openai/gpt-4o

# Docker compose (recommended for prod)
curl -O https://raw.githubusercontent.com/BerriAI/litellm/main/docker-compose.yml
# Edit .env with LITELLM_MASTER_KEY, LITELLM_SALT_KEY, DATABASE_URL
docker compose up
```

Then clients call `http://0.0.0.0:4000/v1/chat/completions` exactly like OpenAI. Admin UI at `/ui` (login with master key).

## Decision flow

- **Prototype / single script** → Python SDK
- **Production app, 1 provider** → Python SDK + Router (for fallbacks)
- **Multiple teams, budgets, audit, guardrails** → Proxy Server
- **Open-source local LLMs (Ollama, vLLM) exposed to apps** → Proxy Server
- **MCP tools as unified endpoint** → Proxy Server with `mcp_servers`

## Skills map (this plugin)

| Skill                         | Purpose                                                           |
| ----------------------------- | ----------------------------------------------------------------- |
| `litellm-python-sdk`          | SDK API reference — completion/acompletion/embedding/stream/tools |
| `litellm-proxy-setup`         | Docker deployment, CLI, Admin UI, VPS integration                 |
| `litellm-config-yaml`         | Full config.yaml reference — all top-level keys                   |
| `litellm-providers-models`    | 100+ providers, model prefixes, required env vars                 |
| `litellm-authentication`      | Virtual keys, master key, JWT, OIDC, RBAC                         |
| `litellm-budgets-spend`       | Budgets per key/team/user/model, rate limits, spend API           |
| `litellm-caching`             | Redis/S3/GCS/disk/semantic cache, TTL, per-request control        |
| `litellm-guardrails-policies` | Presidio PII, Bedrock, Lakera, pre/during/post hooks              |
| `litellm-routing-fallbacks`   | Routing strategies, fallbacks, retries, cooldowns, cost routing   |
| `litellm-logging-metrics`     | Langfuse, OTEL, Prometheus, S3, Slack alerts, custom callbacks    |
| `litellm-mcp-agent-gateway`   | MCP servers, A2A agents, tools via proxy                          |
| `litellm-advanced`            | Custom plugins, secret managers (Vault/AWS/GCP), troubleshooting  |

## Benchmarks

LiteLLM publishes latency benchmarks at `docs.litellm.ai/docs/benchmarks`. Typical overhead:

- SDK in-process: negligible (pass-through)
- Proxy local: <5ms
- Proxy with Redis cache hit: <20ms end-to-end

## IntelliSoins integration target

Deploy on VPS OVH `148.113.174.99`:

- Traefik → `llm.intellisoins.ca` (TLS auto via Let's Encrypt)
- Backend: PostgreSQL existant ou container dédié
- Virtual keys par agent IntelliSoins (pubmed-mcp, masterai, website-intellisoins)
- Callbacks: Langfuse self-host + Prometheus (dashboards Grafana existants)
- Guardrails: Presidio (déjà présent dans stack IntelliSoins pour PII médical)

Voir `litellm-proxy-setup` pour déploiement concret + skill `intellisoins-infrastructure:traefik` pour la config reverse proxy.

## Source

docs.litellm.ai — scraped 2026-04-14.
GitHub: BerriAI/litellm — License MIT (SDK), Enterprise features séparées.
