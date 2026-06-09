---
paths:
  - "**/litellm*messages*"
  - "**/anthropic_messages*"
  - "**/v1/messages*"
---

# LiteLLM Anthropic Messages API (`/v1/messages`)

LiteLLM exposes a native **Anthropic Messages API endpoint** that accepts requests in the Anthropic format and routes them to **any supported provider** (OpenAI, Anthropic, Bedrock, Vertex AI, Gemini, Azure, Azure AI, etc.). LiteLLM follows the [Anthropic messages specification](https://docs.anthropic.com/en/api/messages) for this endpoint — request and response shapes match Anthropic 1:1.

Two ways to consume it:

1. **Proxy Server** — `POST http://0.0.0.0:4000/v1/messages` from any HTTP client (curl, official `anthropic` SDK pointed at the proxy via `base_url=`, etc.).
2. **Python SDK** — `litellm.anthropic.messages.acreate(...)` async function (in-process, no proxy needed).

## When to use this skill vs. neighbours

| Need                                                                                              | Skill                      |
| ------------------------------------------------------------------------------------------------- | -------------------------- |
| `/v1/messages` endpoint, `litellm.anthropic.messages.acreate()`, raw `anthropic` SDK + `base_url` | **this skill**             |
| `claude-agent-sdk` agent loop (Python/TS) via `ANTHROPIC_BASE_URL`                                | `litellm-claude-agent-sdk` |
| OpenAI-format `litellm.completion()` / `acompletion()`                                            | `litellm-python-sdk`       |
| `config.yaml` `model_list` / `router_settings` reference                                          | `litellm-config-yaml`      |
| Provider prefix table (`bedrock/`, `vertex_ai/`, `openai/`, …)                                    | `litellm-providers-models` |
| Virtual key generation, OAuth Max, master key                                                     | `litellm-authentication`   |

## Feature matrix

| Feature           | Status | Notes                                                                              |
| ----------------- | ------ | ---------------------------------------------------------------------------------- |
| Cost tracking     | Yes    | All supported providers                                                            |
| Logging           | Yes    | Langfuse, OTel, Datadog, Prometheus — see `litellm-logging-metrics`                |
| End-user tracking | Yes    | Pass `metadata.user_id`                                                            |
| Streaming         | Yes    | Server-sent events                                                                 |
| Fallbacks         | Yes    | Between supported models — see `litellm-routing-fallbacks`                         |
| Loadbalancing     | Yes    | Between supported models                                                           |
| Guardrails        | Yes    | Input + output text **non-streaming only** — see `litellm-guardrails-policies`     |
| Providers         | All    | `openai`, `anthropic`, `bedrock`, `vertex_ai`, `gemini`, `azure`, `azure_ai`, etc. |

## Python SDK — `litellm.anthropic.messages.acreate()`

In-process async call. Same signature regardless of downstream provider — only the `model=` prefix and credentials change.

### Provider matrix

| Provider         | `model=` value                                                                    | Required env / credentials                                                        |
| ---------------- | --------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| Anthropic        | `anthropic/claude-3-haiku-20240307`, `anthropic/claude-3-7-sonnet-20250219`, etc. | `api_key=` arg or `ANTHROPIC_API_KEY`                                             |
| OpenAI           | `openai/gpt-4`, `openai/gpt-5.1`, etc.                                            | `OPENAI_API_KEY`                                                                  |
| Google AI Studio | `gemini/gemini-2.0-flash-exp`                                                     | `GEMINI_API_KEY`                                                                  |
| Vertex AI        | `vertex_ai/gemini-2.0-flash-exp`                                                  | `VERTEXAI_PROJECT`, `VERTEXAI_LOCATION` + `gcloud auth application-default login` |
| AWS Bedrock      | `bedrock/anthropic.claude-3-sonnet-20240229-v1:0`                                 | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION_NAME`                   |

### Non-streaming (Anthropic)

```python
import litellm

response = await litellm.anthropic.messages.acreate(
    messages=[{"role": "user", "content": "Hello, can you tell me a short joke?"}],
    api_key=api_key,
    model="anthropic/claude-3-haiku-20240307",
    max_tokens=100,
)
```

### Streaming (any provider — example: Bedrock)

```python
import os, litellm
os.environ["AWS_ACCESS_KEY_ID"] = "..."
os.environ["AWS_SECRET_ACCESS_KEY"] = "..."
os.environ["AWS_REGION_NAME"] = "us-west-2"

response = await litellm.anthropic.messages.acreate(
    messages=[{"role": "user", "content": "Hello, can you tell me a short joke?"}],
    model="bedrock/anthropic.claude-3-sonnet-20240229-v1:0",
    max_tokens=100,
    stream=True,
)
async for chunk in response:
    print(chunk)
```

For OpenAI / Gemini / Vertex AI variants, swap `model=` and the env vars per the provider matrix above. Signature otherwise identical.

## Proxy Server — `POST /v1/messages`

Production gateway path. Define the model in `config.yaml`, start the proxy, then any Anthropic-format client works.

### Minimal config

```yaml
model_list:
  - model_name: anthropic-claude
    litellm_params:
      model: claude-3-7-sonnet-latest
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: bedrock-claude
    litellm_params:
      model: bedrock/anthropic.claude-3-sonnet-20240229-v1:0
      aws_access_key_id: os.environ/AWS_ACCESS_KEY_ID
      aws_secret_access_key: os.environ/AWS_SECRET_ACCESS_KEY
      aws_region_name: us-west-2

  - model_name: openai-gpt4
    litellm_params:
      model: openai/gpt-4
      api_key: os.environ/OPENAI_API_KEY

  - model_name: gemini-2-flash
    litellm_params:
      model: gemini/gemini-2.0-flash-exp
      api_key: os.environ/GEMINI_API_KEY

  - model_name: vertex-gemini
    litellm_params:
      model: vertex_ai/gemini-2.0-flash-exp
      vertex_project: your-gcp-project-id
      vertex_location: us-central1
```

```bash
litellm --config /path/to/config.yaml
```

### Client A — official `anthropic` Python SDK pointed at the proxy

```python
import anthropic

client = anthropic.Anthropic(
    base_url="http://0.0.0.0:4000",   # or https://llm.intellisoins.ca
    api_key="sk-1234",                # LiteLLM virtual key or master key
)

response = client.messages.create(
    messages=[{"role": "user", "content": "Hello, can you tell me a short joke?"}],
    model="anthropic-claude",          # matches model_name in config.yaml
    max_tokens=100,
)
```

The exact same `client` works against `bedrock-claude`, `openai-gpt4`, `gemini-2-flash`, `vertex-gemini` — just change `model=`. LiteLLM translates Anthropic Messages → provider format → Anthropic Messages on the response.

### Client B — raw curl

```bash
curl -L -X POST 'http://0.0.0.0:4000/v1/messages' \
  -H 'content-type: application/json' \
  -H 'x-api-key: $LITELLM_API_KEY' \
  -H 'anthropic-version: 2023-06-01' \
  -d '{
    "model": "anthropic-claude",
    "messages": [
      {"role": "user", "content": "Hello, can you tell me a short joke?"}
    ],
    "max_tokens": 100
  }'
```

`anthropic-version: 2023-06-01` is the standard Anthropic API version header — LiteLLM accepts and forwards it.

## Request format

Body follows the [Anthropic messages spec](https://docs.anthropic.com/en/api/messages) verbatim.

### Required

| Field        | Type    | Notes                                                                                                                     |
| ------------ | ------- | ------------------------------------------------------------------------------------------------------------------------- |
| `model`      | string  | Either an Anthropic model id (SDK direct, e.g. `claude-3-7-sonnet-20250219`) or a `model_name` from `config.yaml` (Proxy) |
| `max_tokens` | integer | Must be > 1. Model may stop earlier                                                                                       |
| `messages`   | array   | Ordered turns. Each: `{"role": "user"\|"assistant", "content": string \| content_blocks[]}`                               |

`content` shorthand equivalence:

```json
{ "role": "user", "content": "Hello, Claude" }
```

is equivalent to:

```json
{ "role": "user", "content": [{ "type": "text", "text": "Hello, Claude" }] }
```

### Optional

| Field            | Notes                                                                                                                                                                                                                           |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `metadata`       | `{"user_id": "..."}` opaque end-user identifier (used for spend tracking)                                                                                                                                                       |
| `stop_sequences` | Array of strings                                                                                                                                                                                                                |
| `stream`         | Boolean — server-sent events                                                                                                                                                                                                    |
| `system`         | String or content-block array — system prompt                                                                                                                                                                                   |
| `temperature`    | `0 < t < 1`                                                                                                                                                                                                                     |
| `thinking`       | `{"type": "enabled", "budget_tokens": >=1024 and < max_tokens, "summary": "auto"\|"concise"\|"detailed"\|"disabled"}`. **`summary` is preserved and forwarded** when routing to non-Anthropic providers (e.g. `openai/gpt-5.1`) |
| `tool_choice`    | Tool-selection strategy                                                                                                                                                                                                         |
| `tools`          | Array of `{name, description, input_schema}`                                                                                                                                                                                    |
| `top_k`          | Top-K sampling                                                                                                                                                                                                                  |
| `top_p`          | `0 < p < 1` nucleus sampling                                                                                                                                                                                                    |

## Response format

```json
{
  "content": [{ "text": "Hi! My name is Claude.", "type": "text" }],
  "id": "msg_013Zva2CMHLNnXjNJJKqJ2EF",
  "model": "claude-3-7-sonnet-20250219",
  "role": "assistant",
  "stop_reason": "end_turn",
  "stop_sequence": null,
  "type": "message",
  "usage": {
    "input_tokens": 2095,
    "output_tokens": 503,
    "cache_creation_input_tokens": 2095,
    "cache_read_input_tokens": 0
  }
}
```

### `content[].type`

- `text` — generated text. Up to 5,000,000 characters.
- `tool_use` — model invoked a tool.
- `thinking` — extended-thinking trace (when `thinking.type == "enabled"`).
- `redacted_thinking` — encrypted/redacted thinking block.

### Citations (per content block, optional)

When the model attaches citations:

```json
{
  "cited_text": "...",
  "document_index": 0,
  "document_title": "...",
  "start_char_index": 12,
  "end_char_index": 48,
  "type": "char_location"
}
```

### `stop_reason`

| Value           | Meaning                                                                    |
| --------------- | -------------------------------------------------------------------------- |
| `end_turn`      | Natural stop                                                               |
| `max_tokens`    | Hit `max_tokens` cap                                                       |
| `stop_sequence` | Hit a value in `stop_sequences` (the matched string is in `stop_sequence`) |
| `tool_use`      | Model called one or more tools                                             |

### `usage` — billing & cache

| Field                         | Notes                                             |
| ----------------------------- | ------------------------------------------------- |
| `input_tokens`                | Prompt tokens processed                           |
| `output_tokens`               | Completion tokens generated                       |
| `cache_creation_input_tokens` | Tokens written into the prompt cache (write path) |
| `cache_read_input_tokens`     | Tokens read from the prompt cache (cheap path)    |

LiteLLM forwards these counters from Anthropic verbatim and computes spend per-key/user/team using them — see `litellm-budgets-spend`.

## Structured output (`output_format`)

Schema-constrained JSON output via the `output_format` parameter on `/v1/messages`. The endpoint returns valid JSON matching the supplied JSON Schema, embedded as a string in `content[0].text`.

### Provider support

| Provider                     | `model=` value (example)                                          | Notes                                                                |
| ---------------------------- | ----------------------------------------------------------------- | -------------------------------------------------------------------- |
| Anthropic                    | `anthropic/claude-sonnet-4-5-20250514`                            | Native                                                               |
| Azure AI (Anthropic)         | `azure_ai/claude-sonnet-4-5-20250514`                             | Claude on Azure AI inference endpoints — requires `api_base`         |
| Bedrock Converse (Anthropic) | `bedrock/global.anthropic.claude-sonnet-4-5-20250929-v1:0`        | Default Bedrock path                                                 |
| Bedrock Invoke (Anthropic)   | `bedrock/invoke/global.anthropic.claude-sonnet-4-5-20250929-v1:0` | Force Invoke API instead of Converse — prefix with `bedrock/invoke/` |

OpenAI / Gemini / Vertex Gemini are **NOT** in the support matrix for `output_format` on `/v1/messages`. For those, use `litellm.completion(..., response_format={"type": "json_schema", ...})` — skill `litellm-python-sdk`.

### `output_format` field

Add `output_format` alongside `messages` / `max_tokens`:

```json
{
  "output_format": {
    "type": "json_schema",
    "schema": {
      "type": "object",
      "properties": {
        "name": { "type": "string" },
        "email": { "type": "string" },
        "plan_interest": { "type": "string" },
        "demo_requested": { "type": "boolean" }
      },
      "required": ["name", "email", "plan_interest", "demo_requested"],
      "additionalProperties": false
    }
  }
}
```

| Field                         | Notes                                                                                       |
| ----------------------------- | ------------------------------------------------------------------------------------------- |
| `type`                        | Must be `"json_schema"`                                                                     |
| `schema.type`                 | Root type — typically `"object"`                                                            |
| `schema.properties`           | Field definitions (JSON Schema syntax)                                                      |
| `schema.required`             | Required field names                                                                        |
| `schema.additionalProperties` | Set `false` to enforce strict schema adherence — without it the model may emit extra fields |

### Example — Anthropic via Proxy

`config.yaml`:

```yaml
model_list:
  - model_name: claude-sonnet
    litellm_params:
      model: anthropic/claude-sonnet-4-5-20250514
      api_key: os.environ/ANTHROPIC_API_KEY
```

curl:

```bash
curl http://localhost:4000/v1/messages \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-sonnet",
    "max_tokens": 1024,
    "messages": [
      {"role": "user", "content": "Extract the key information from this email: John Smith (john@example.com) is interested in our Enterprise plan and wants to schedule a demo for next Tuesday at 2pm."}
    ],
    "output_format": {
      "type": "json_schema",
      "schema": {
        "type": "object",
        "properties": {
          "name":           {"type": "string"},
          "email":          {"type": "string"},
          "plan_interest":  {"type": "string"},
          "demo_requested": {"type": "boolean"}
        },
        "required": ["name", "email", "plan_interest", "demo_requested"],
        "additionalProperties": false
      }
    }
  }'
```

### Switching providers

Only the `model_list` entry changes — the curl body stays identical apart from `model=`:

```yaml
# Azure AI (Anthropic)
- model_name: azure-claude-sonnet
  litellm_params:
    model: azure_ai/claude-sonnet-4-5-20250514
    api_key: os.environ/AZURE_AI_API_KEY
    api_base: https://your-endpoint.inference.ai.azure.com

# Bedrock Converse (default)
- model_name: bedrock-claude-sonnet
  litellm_params:
    model: bedrock/global.anthropic.claude-sonnet-4-5-20250929-v1:0
    aws_access_key_id: os.environ/AWS_ACCESS_KEY_ID
    aws_secret_access_key: os.environ/AWS_SECRET_ACCESS_KEY
    aws_region_name: us-west-2

# Bedrock Invoke (force Invoke API instead of Converse)
- model_name: bedrock-claude-invoke
  litellm_params:
    model: bedrock/invoke/global.anthropic.claude-sonnet-4-5-20250929-v1:0
    aws_access_key_id: os.environ/AWS_ACCESS_KEY_ID
    aws_secret_access_key: os.environ/AWS_SECRET_ACCESS_KEY
    aws_region_name: us-west-2
```

### Response shape

The schema-conformant JSON arrives as a **string** inside `content[0].text` — still a `text` block. Caller parses it with `json.loads(...)` / `JSON.parse(...)`.

```json
{
  "id": "msg_01XFDUDYJgAACzvnptvVoYEL",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "{\"name\":\"John Smith\",\"email\":\"john@example.com\",\"plan_interest\":\"Enterprise\",\"demo_requested\":true}"
    }
  ],
  "model": "claude-sonnet-4-5-20250514",
  "stop_reason": "end_turn",
  "stop_sequence": null,
  "usage": { "input_tokens": 75, "output_tokens": 28 }
}
```

### Gotchas

- `content[0].text` is a JSON string, **not a parsed object** — caller is responsible for parsing.
- Schema is forwarded as-is to the model. Always include `additionalProperties: false` for strict adherence.
- `Bedrock Converse` (default) vs `Bedrock Invoke` (`bedrock/invoke/...` prefix): Converse is the recommended unified API; Invoke is the legacy per-provider format. Use Invoke only when a Converse-incompatible feature is required.

## Edge cases & gotchas

- **Guardrails on streaming**: input + output guardrails apply on **non-streaming** only. Streaming responses are uncensored — design rails accordingly. See `litellm-guardrails-policies`.
- **`thinking` cross-provider**: LiteLLM preserves `summary` (`auto`/`concise`/`detailed`/`disabled`) when routing to non-Anthropic backends like `openai/gpt-5.1`. The downstream provider receives it intact even though the field originates in the Anthropic spec.
- **`anthropic-version` header**: standard Anthropic API value `2023-06-01`. LiteLLM accepts it; not required for the Python SDK call but mandatory for raw HTTP if your client mimics the official Anthropic flow.
- **Model name mismatch**: Proxy users must match `model=` to a `model_name` in `config.yaml` (case-sensitive). Common cause of `400` / `model not found` errors.
- **Cache fields are always present**: `cache_creation_input_tokens` / `cache_read_input_tokens` are returned even when prompt caching is not active (both `0`). Don't gate logic on field presence — gate on the integer value.

## Cross-references

| Skill                       | Boundary                                                                                                                            |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `litellm-claude-agent-sdk`  | When you want a full **agent loop** (`ClaudeSDKClient`, `query()`) routed via `ANTHROPIC_BASE_URL` instead of raw `messages.create` |
| `litellm-python-sdk`        | When you want OpenAI-format `litellm.completion()` instead of Anthropic-format `litellm.anthropic.messages.acreate()`               |
| `litellm-config-yaml`       | Full `model_list` / `router_settings` / `general_settings` reference                                                                |
| `litellm-providers-models`  | Provider prefix table + required env vars for `model_list`                                                                          |
| `litellm-authentication`    | Virtual keys (`x-api-key`), master key, OAuth Max, JWT                                                                              |
| `litellm-routing-fallbacks` | Multi-deployment fallback chains for `/v1/messages`                                                                                 |
| `litellm-budgets-spend`     | Spend tracking from `usage` counters per key/user/team                                                                              |
| `litellm-logging-metrics`   | Langfuse / OTel / Prometheus traces of `/v1/messages` calls                                                                         |

## IntelliSoins context

Local Proxy: `http://localhost:8092/v1/messages` (master_key in Keychain). Production: `https://llm.intellisoins.ca/v1/messages` via Traefik. Both accept the official `anthropic` Python SDK with `base_url=` + virtual key, and raw curl with `x-api-key` + `anthropic-version: 2023-06-01`. See auto-memory `project_litellm_gateway.md` for the dual auth pattern (master_key vs OAuth Max).
