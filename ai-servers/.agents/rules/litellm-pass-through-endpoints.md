---
paths:
  - "**/litellm*pass*through*"
  - "**/litellm/passthrough*"
  - "**/litellm-*/passthrough*"
  - "**/pass_through*"
---

# LiteLLM Pass-Through Endpoints

LiteLLM exposes **Pass-Through Endpoints** — routes shaped as `/{provider}/{native_path}` that forward the request body **as-is** to the upstream provider API. No format translation. The native provider SDK works unchanged: only the `base_url` changes.

What LiteLLM still adds on the side: **Virtual Key auth, cost tracking, structured logging callbacks, end-user/team tagging, spend budgets, guardrails (non-streaming)**. The provider sees the request body it expects; the client sees the response shape it expects; LiteLLM observes both transparently.

VERIFIE: <https://docs.litellm.ai/docs/pass_through/intro> (upstream doc, retrieved 2026-05-06).
VERIFIE: code source `~/.venvs/litellm/lib/python3.12/site-packages/litellm/proxy/pass_through_endpoints/` (11 provider handlers + `passthrough_endpoint_router.py`).

## 1. When to use this skill vs. neighbours

The single most common confusion: `/v1/messages` (LiteLLM-canonical, **translated**) vs `/anthropic/v1/messages` (pass-through, **raw**). They look similar; they are different routes with different semantics.

| Route                                                                                                       | Format             | Translation                                                                     | Use when                                                                                                                                                                            |
| ----------------------------------------------------------------------------------------------------------- | ------------------ | ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/v1/messages`                                                                                              | Anthropic Messages | LiteLLM **translates** to any backend (OpenAI, Bedrock, Vertex, Gemini, Azure…) | You want one API shape across multi-provider routing, fallbacks, loadbalancing → see skill `litellm-anthropic-messages-api`                                                         |
| `/anthropic/v1/messages`                                                                                    | Anthropic Messages | **No translation** — forwarded raw to `api.anthropic.com`                       | You need Anthropic-only features (Batches API, count_tokens beta, custom `anthropic-beta:` headers), or you're migrating an existing native Anthropic SDK codebase → **this skill** |
| `/{provider}/{native_path}` (vertex_ai, cohere, bedrock, gemini, mistral, assemblyai, openai, azure, vllm…) | Provider-native    | **No translation**                                                              | Same logic as above, applied to other providers → **this skill**                                                                                                                    |
| `/v1/chat/completions`, `/v1/embeddings`, `/v1/ocr`, etc.                                                   | OpenAI-style       | LiteLLM normalises across providers                                             | Generic OpenAI-compatible workflows → see `litellm-python-sdk`, `litellm-providers-models`                                                                                          |

Other neighbours that own narrower scope:

| Need                                                     | Skill                                                                                                                        |
| -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Virtual Keys lifecycle (generate, rotate, scopes)        | `litellm-authentication`                                                                                                     |
| `config.yaml` general reference                          | `litellm-config-yaml`                                                                                                        |
| OCR-only pass-through (Tesseract, Docling, Apple Vision) | `litellm-ocr`                                                                                                                |
| MCP servers as pass-through                              | `litellm-mcp-agent-gateway`                                                                                                  |
| Logging callbacks (Langfuse, OTel, Datadog, Prometheus)  | `litellm-logging-metrics`                                                                                                    |
| Guardrails (Presidio, AIM, etc.)                         | `litellm-guardrails-policies`                                                                                                |
| `/v1/messages/count_tokens` LiteLLM-canonical            | `litellm-count-tokens` (the pass-through `/anthropic/v1/messages/count_tokens` is covered here in `references/anthropic.md`) |

## 2. Concept and request flow

Pass-through routes do five things server-side:

1. **Receive** the client request at `/{provider}/{native_path}` with a LiteLLM Virtual Key (Bearer or `x-api-key`).
2. **Validate** the Virtual Key (`UserAPIKeyAuth`) — check spend, expiry, `models_allowed`, team membership.
3. **Resolve credentials** — `passthrough_endpoint_router.get_credentials(custom_llm_provider, region_name)` swaps the VK for the provider's native API key (Anthropic `x-api-key`, Vertex OAuth Bearer, AWS SigV4, Cohere Bearer, etc.).
4. **Forward** to the upstream URL with native auth + native headers + native body, preserving streaming when applicable.
5. **Observe** — async logging callback fires after the response with cost, token usage, user/team tags, latency.

VERIFIE: code source `~/.venvs/litellm/lib/python3.12/site-packages/litellm/proxy/pass_through_endpoints/passthrough_endpoint_router.py` (`get_credentials` method).

### Auth header swap

| Hop                | Header sent                                                                                                                                                                                                             |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Client → LiteLLM   | `Authorization: Bearer <litellm_virtual_key>` (or `x-api-key: <vk>`)                                                                                                                                                    |
| LiteLLM → Provider | Provider-native: `x-api-key: sk-ant-...` (Anthropic), `Authorization: Bearer <gcp_oauth>` (Vertex), AWS SigV4 (Bedrock), `Authorization: Bearer <cohere_key>`, `?key=<gemini_key>` (Gemini AI Studio query param), etc. |

The native key never leaves the LiteLLM server. Clients only ever see their VK.

### Error codes

| Code | Origin               | Cause                                                                                                                 |
| ---- | -------------------- | --------------------------------------------------------------------------------------------------------------------- |
| 401  | LiteLLM              | Missing / invalid / expired Virtual Key, missing `x-api-key`                                                          |
| 401  | Provider (forwarded) | LiteLLM-side native key is wrong/expired (config issue)                                                               |
| 400  | LiteLLM              | Malformed body, missing required header (`anthropic-version`)                                                         |
| 400  | Provider (forwarded) | Invalid `model` id, schema violation                                                                                  |
| 404  | LiteLLM              | `/{provider}` path not registered (provider not in `model_list` and not in `general_settings.pass_through_endpoints`) |
| 429  | Provider (forwarded) | Rate limit at provider; LiteLLM does not auto-retry pass-through 429s                                                 |
| 429  | LiteLLM              | VK spend cap or team budget exceeded                                                                                  |
| 5xx  | Provider (forwarded) | Upstream outage                                                                                                       |
| 500  | LiteLLM              | Credential resolution failure (env var missing, expired GCP token)                                                    |

## 3. Supported providers

| Provider         | Route prefix                                               | Auth (LiteLLM → upstream)                 | Streaming | Cost tracking                   | Details                                            |
| ---------------- | ---------------------------------------------------------- | ----------------------------------------- | --------- | ------------------------------- | -------------------------------------------------- |
| Anthropic        | `/anthropic/{path}`                                        | `x-api-key: sk-ant-...`                   | SSE       | All endpoints                   | [references/anthropic.md](references/anthropic.md) |
| Vertex AI        | `/vertex_ai/{path}` (also `/vertex-ai/{path}`)             | OAuth Bearer (auto-refresh)               | SSE       | Token-based via `usageMetadata` | [references/vertex_ai.md](references/vertex_ai.md) |
| Cohere           | `/cohere/{path}`                                           | `Authorization: Bearer <COHERE_API_KEY>`  | SSE       | Chat + Embed                    | [references/cohere.md](references/cohere.md)       |
| Bedrock          | `/bedrock/{path}`                                          | AWS SigV4 (botocore)                      | SSE       | Invoke + Converse               | [references/bedrock.md](references/bedrock.md)     |
| Gemini AI Studio | `/gemini/{path}`                                           | Query param `?key=<GEMINI_API_KEY>`       | SSE       | Yes                             | [references/gemini.md](references/gemini.md)       |
| Mistral          | `/mistral/{path}`                                          | `Authorization: Bearer <MISTRAL_API_KEY>` | SSE       | Chat                            | [references/others.md](references/others.md)       |
| AssemblyAI       | `/assemblyai/{path}` (also `/eu.assemblyai/{path}`)        | `Authorization: <ASSEMBLYAI_API_KEY>`     | WebSocket | Async polling                   | [references/others.md](references/others.md)       |
| OpenAI raw       | `/openai/{path}` (also `/openai_passthrough/{path}`)       | `Authorization: Bearer sk-...`            | SSE       | All                             | [references/others.md](references/others.md)       |
| Azure native     | `/azure/{path}` (also `/azure_ai/{path}`)                  | `api-key: <AZURE_KEY>`                    | SSE       | Yes                             | [references/others.md](references/others.md)       |
| VLLM             | `/vllm/{path}`                                             | Optional (local)                          | SSE       | Manual via `cost_per_request`   | [references/others.md](references/others.md)       |
| Generic custom   | configured under `general_settings.pass_through_endpoints` | Headers in config (env vars supported)    | Yes       | `cost_per_request` static       | See section 5 below                                |

VERIFIE: <https://docs.litellm.ai/docs/pass_through/intro> + per-provider docs (anthropic_completion, vertex_ai, cohere, bedrock, google_ai_studio, mistral, assembly_ai, openai_passthrough, azure, vllm).

Routes are **auto-registered** when a matching `model_list` entry exists (e.g. listing any `vertex_ai/*` model auto-mounts `/vertex_ai/{path}`). The `general_settings.pass_through_endpoints` block is for providers without a `model_list` entry, or for custom HTTP services.

## 4. Quick start

Examples use Michael's local proxy on `127.0.0.1:8092` with the master key from macOS Keychain. Replace with a Virtual Key in production.

```bash
MASTER=$(security find-generic-password -a "$USER" -s litellm-master-key -w)
```

### Anthropic — raw curl to `/anthropic/v1/messages`

```bash
curl -X POST 'http://127.0.0.1:8092/anthropic/v1/messages' \
  -H "x-api-key: $MASTER" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-3-7-sonnet-20250219",
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Hi"}]
  }'
```

The body is forwarded verbatim to `https://api.anthropic.com/v1/messages`. The response shape is exactly what Anthropic returns. LiteLLM logs cost + tokens + VK metadata to the side.

### Anthropic — official Python SDK pointed at LiteLLM

```python
import os
from anthropic import Anthropic

client = Anthropic(
    base_url="http://127.0.0.1:8092/anthropic",   # NOTE: /anthropic prefix
    api_key=os.environ["LITELLM_VK"],             # Virtual Key, not sk-ant-...
)

resp = client.messages.create(
    model="claude-3-7-sonnet-20250219",
    max_tokens=200,
    messages=[{"role": "user", "content": "Hello"}],
)
print(resp.content[0].text)
```

The Anthropic SDK works unchanged because LiteLLM honours the Anthropic protocol byte-for-byte at this prefix. Contrast this with `litellm-anthropic-messages-api` where `base_url=http://.../` (no provider prefix) routes through the LiteLLM-canonical `/v1/messages` translator.

### Vertex AI — curl to `/vertex_ai/v1/projects/.../generateContent`

```bash
curl -X POST \
  "http://127.0.0.1:8092/vertex_ai/v1/projects/MY-PROJECT/locations/us-central1/publishers/google/models/gemini-2.0-flash-exp:generateContent" \
  -H "Authorization: Bearer $MASTER" \
  -H "content-type: application/json" \
  -d '{"contents": [{"role": "user", "parts": [{"text": "Hi"}]}]}'
```

LiteLLM strips the `Authorization: Bearer $MASTER`, validates the VK, then re-signs with the GCP service-account OAuth token resolved from `vertex_credentials` / `vertex_project` / `vertex_location` (config) or `GOOGLE_APPLICATION_CREDENTIALS` (env).

## 5. Configuring custom pass-through endpoints

For providers not auto-mounted via `model_list`, declare them under `general_settings.pass_through_endpoints` in `config.yaml`.

```yaml
general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  pass_through_endpoints:
    - path: "/bria" # required — route prefix on LiteLLM
      target: "https://engine.prod.bria-api.com" # required — upstream base URL
      include_subpath: true # forward subpath (e.g. /api/v1/imagine)
      forward_headers: true # forward ALL client headers (use cautiously)
      headers: # inject server-side headers (env vars supported)
        Authorization: "os.environ/BRIA_API_KEY"
        x-custom-header: "static-value"
      query_params: # default query params appended
        api_version: "2024-01-01"
      cost_per_request: 0.05 # static USD cost per call (logged on success)
      methods: ["POST", "GET"] # allowed HTTP methods (default: all)
```

VERIFIE: <https://docs.litellm.ai/docs/proxy/pass_through> (upstream doc, retrieved 2026-05-06) + code `~/.venvs/litellm/.../pass_through_endpoints/pass_through_endpoints.py`.

| Param              | Required | Default | Purpose                                                                                                                                                                     |
| ------------------ | -------- | ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `path`             | yes      | —       | Route prefix mounted on LiteLLM (e.g. `/bria`, `/my-internal-svc`)                                                                                                          |
| `target`           | yes      | —       | Upstream base URL the request is forwarded to                                                                                                                               |
| `include_subpath`  | no       | `false` | If `true`, append the subpath after `path` to `target` (so `/bria/api/v1/imagine` → `<target>/api/v1/imagine`)                                                              |
| `forward_headers`  | no       | `false` | If `true`, all client headers are forwarded upstream (in addition to `headers:`). Risk: leaks LiteLLM `Authorization` if not stripped — leave `false` unless you've audited |
| `headers`          | no       | `{}`    | Server-side headers injected per request. Supports `os.environ/<VAR>` for secrets                                                                                           |
| `query_params`     | no       | `{}`    | Default query params appended to every forwarded request                                                                                                                    |
| `cost_per_request` | no       | `0`     | Static USD cost logged for every successful response (token-based tracking unavailable for custom endpoints)                                                                |
| `methods`          | no       | all     | Whitelist of HTTP methods. Use `["POST"]` to forbid GET, etc.                                                                                                               |

Routes auto-mount on proxy startup. Reload the proxy after editing `config.yaml`.

## 6. Virtual Keys + pass-through

Virtual Keys behave identically here as for any other LiteLLM route. The lifecycle (creation, rotation, scopes) lives in `litellm-authentication`; this skill only highlights the pass-through-specific bits.

| VK feature              | Pass-through behaviour                                                                                                                                                              |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `models_allowed`        | Restricts which `model=` values (in body) and which `/{provider}/...` prefixes the key can hit. Example: a VK scoped to `["anthropic/claude-3-haiku"]` cannot call `/vertex_ai/...` |
| `spend` cap             | Enforced before forwarding. 429 if cap exceeded — request never leaves LiteLLM                                                                                                      |
| `team_id`               | Tags pass-through call into team budget bucket                                                                                                                                      |
| `metadata`              | Propagated into logging callbacks (Langfuse, OTel)                                                                                                                                  |
| `tpm`/`rpm` rate limits | Enforced before forwarding                                                                                                                                                          |

Master key bypasses `models_allowed` (admin-grade). For multi-tenant or per-team usage, generate scoped VKs.

## 7. End-user tracking, cost, and logging

Three orthogonal mechanisms — pick whichever fits your client SDK.

### Method A — `x-litellm-tags` header

```bash
curl ... \
  -H "x-litellm-tags: user_id=patient-42,session=2026-05-06,team=cardio"
```

Tags land in `LiteLLM_SpendLogs.metadata` and in any logging callback.

### Method B — `litellm_metadata` body field

```bash
-d '{
  "model": "claude-3-7-sonnet-20250219",
  "messages": [...],
  "max_tokens": 100,
  "litellm_metadata": {
    "user_id": "patient-42",
    "session_id": "2026-05-06-T0930",
    "tags": ["cardio", "PHI"]
  }
}'
```

LiteLLM strips `litellm_metadata` before forwarding to the provider (Anthropic/Vertex/etc. never see it). Use when you can't add custom HTTP headers (e.g. some browser environments, signed URLs).

### Method C — provider-native metadata (Anthropic only)

Anthropic's own spec accepts `metadata.user_id`. LiteLLM forwards it intact and **also** indexes it for spend tracking.

```json
{"model": "claude-...", "messages": [...], "metadata": {"user_id": "patient-42"}}
```

### Cost tracking

| Provider                                          | Source of cost                                                                                                              |
| ------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Anthropic, OpenAI, Mistral, Cohere, Gemini, Azure | Token usage from native response (`usage.input_tokens`, `usage.output_tokens`) × per-model price in LiteLLM's pricing table |
| Vertex AI                                         | `usageMetadata.{prompt,candidates,total}TokenCount` (multi-modal: text + audio + video aggregated)                          |
| Bedrock                                           | Native `usage` (Converse) or counted from `body` (Invoke)                                                                   |
| AssemblyAI                                        | Async — `AssemblyAIPassthroughLoggingHandler` polls transcript completion and logs cost when ready                          |
| VLLM                                              | No native usage — set `cost_per_request: <float>` in config to log a flat cost                                              |
| Generic custom                                    | Same — `cost_per_request: <float>`                                                                                          |

### Logging

All standard LiteLLM callbacks fire on pass-through calls (Langfuse, OpenTelemetry, Datadog, Prometheus, S3, GCS). Trace contains: VK id, user_id/team_id, provider, native endpoint, latency, cost, request body (configurable redaction), response shape. See `litellm-logging-metrics`.

## 8. Local context (Michael)

Local proxy: `http://127.0.0.1:8092` — master key stored in macOS Keychain (service `litellm-master-key`, account `$USER`). Production: `https://llm.intellisoins.ca` via Traefik.

Auto-memory: `~/.claude/projects/-Users-michaelahern-ai-servers/memory/project_litellm_gateway.md`.

```bash
# Anthropic pass-through using local proxy + master key
MASTER=$(security find-generic-password -a "$USER" -s litellm-master-key -w)
curl -X POST 'http://127.0.0.1:8092/anthropic/v1/messages' \
  -H "x-api-key: $MASTER" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-sonnet-4-6",
    "max_tokens": 50,
    "messages": [{"role": "user", "content": "ping"}]
  }'
```

For PHI / Loi 25 workloads, prefer providers with Canadian data residency: Bedrock `ca-central-1` (Anthropic Claude on AWS Canada), Azure Canada Central / Canada East, Vertex AI `northamerica-northeast1` (Montréal). See auto-memory `topic_data_residency_canada_llm.md`. Pure pass-through preserves data flow exactly as the provider documents — no LiteLLM-side translation that could change residency semantics.

## 9. Cross-references

| Skill                            | Boundary                                                                                                                                        |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `litellm-anthropic-messages-api` | LiteLLM-canonical `/v1/messages` (translated, multi-provider). Use when you want one shape across backends                                      |
| `litellm-authentication`         | Virtual Keys lifecycle, OAuth Max, master key, JWT                                                                                              |
| `litellm-config-yaml`            | Full `general_settings` / `model_list` / `router_settings` reference                                                                            |
| `litellm-providers-models`       | Provider prefix table for `model_list` entries (which auto-mount pass-through routes)                                                           |
| `litellm-ocr`                    | Pass-through OCR (Tesseract / Docling / Apple Vision) — narrower scope                                                                          |
| `litellm-mcp-agent-gateway`      | Pass-through MCP servers                                                                                                                        |
| `litellm-count-tokens`           | Canonical `/v1/messages/count_tokens` (translated). The pass-through `/anthropic/v1/messages/count_tokens` is in `references/anthropic.md` here |
| `litellm-logging-metrics`        | Langfuse / OTel / Datadog / Prometheus configuration                                                                                            |
| `litellm-budgets-spend`          | Spend caps, team budgets, retention                                                                                                             |
| `litellm-guardrails-policies`    | Presidio / AIM / Lakera (non-streaming only on pass-through)                                                                                    |
