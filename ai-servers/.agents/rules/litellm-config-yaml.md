---
paths:
  - "**/litellm/config*.yaml"
  - "**/litellm-*/config*.yaml"
  - "**/litellm/config*.yml"
  - "**/litellm-*/config*.yml"
---

# LiteLLM config.yaml Reference

Single source-of-truth file for the Proxy. Six top-level keys. Environment vars loaded via `os.environ/VAR_NAME` syntax.

## Top-level keys

| Key                     | Purpose                                                            |
| ----------------------- | ------------------------------------------------------------------ |
| `model_list`            | Define available models (deployment-level)                         |
| `router_settings`       | Routing strategy, load balancing, Redis sync                       |
| `litellm_settings`      | SDK-level settings (callbacks, fallbacks, cache, retries)          |
| `general_settings`      | Server config (master key, DB, alerting, auth)                     |
| `environment_variables` | Proxy process env vars                                             |
| `credential_list`       | Centralized credential sets (reusable across models)               |
| `guardrails`            | Content filters, PII masking (skill `litellm-guardrails-policies`) |
| `mcp_servers`           | MCP tool gateway (skill `litellm-mcp-agent-gateway`)               |

---

## model_list

Required. Each entry: one deployment.

```yaml
model_list:
  - model_name: gpt-4o # user-facing name
    litellm_params:
      model: azure/gpt-4o-eu # provider prefix + deployment id
      api_base: https://endpoint.openai.azure.com/
      api_key: os.environ/AZURE_API_KEY
      api_version: "2023-05-15"
      temperature: 0.2
      max_tokens: 2000
      rpm: 6 # rate limit (requests/min)
      tpm: 1000 # rate limit (tokens/min)
      timeout: 30
    model_info:
      version: 2
      supported_environments: ["production", "staging"]
      access_groups: ["beta-models"]
```

### litellm_params sub-keys

| Param                                            | Type     | Notes                                      |
| ------------------------------------------------ | -------- | ------------------------------------------ |
| `model`                                          | str      | **Required**. Format `provider/model-id`   |
| `api_base`                                       | str      | Custom endpoint URL                        |
| `api_key`                                        | str      | Supports `os.environ/VAR`                  |
| `api_version`                                    | str      | Provider-specific                          |
| `temperature` / `max_tokens` / `seed`            | num      | Default overrides                          |
| `rpm` / `tpm`                                    | int      | Deployment rate limits                     |
| `organization`                                   | str/list | OpenAI org ID(s)                           |
| `extra_headers`                                  | dict     | Custom HTTP headers                        |
| `aws_region_name`                                | str      | Bedrock/SageMaker                          |
| `aws_access_key_id` / `aws_secret_access_key`    | str      | AWS creds                                  |
| `vertex_project` / `vertex_location`             | str      | Vertex AI                                  |
| `input_cost_per_token` / `output_cost_per_token` | float    | Custom pricing                             |
| `weight`                                         | int      | For simple-shuffle weighted routing        |
| `order`                                          | int      | Priority fallback order (lower = higher)   |
| `cooldown_time`                                  | int      | Per-deployment cooldown override (seconds) |
| `max_parallel_requests`                          | int      | Per-deployment concurrency                 |
| `litellm_credential_name`                        | str      | Reference to credential_list entry         |

### Wildcard models

```yaml
model_list:
  - model_name: "*"
    litellm_params:
      model: "*" # accepts any model with default provider creds
```

---

## router_settings

Load balancing and multi-instance coordination.

```yaml
router_settings:
  routing_strategy: simple-shuffle # default
  # Options: simple-shuffle, least-busy, usage-based-routing, latency-based-routing, cost-based-routing

  model_group_alias:
    gpt-4: gpt-4o # alias old names to new

  num_retries: 2
  timeout: 30
  retry_after: 5 # minimum seconds between retries

  allowed_fails: 3 # cooldown after N failures/min
  cooldown_time: 30 # seconds

  # Redis for distributed rate limits + routing state
  redis_host: os.environ/REDIS_HOST
  redis_port: 6379
  redis_password: os.environ/REDIS_PASSWORD

  enable_pre_call_check: true # filter by context window + region

  routing_strategy_args:
    ttl: 10 # latency cache window (seconds)
    lowest_latency_buffer: 0.5 # prevent overload (50% buffer)
```

Detail: skill `litellm-routing-fallbacks`.

---

## litellm_settings

SDK-level behavior (applies to every call).

```yaml
litellm_settings:
  drop_params: true # silently drop provider-unsupported params
  set_verbose: false
  json_logs: true

  num_retries: 3
  request_timeout: 30

  # Callbacks (observability)
  success_callback: ["langfuse", "prometheus"]
  failure_callback: ["sentry", "slack"]
  callbacks: ["otel"] # both success + failure

  # Fallbacks
  fallbacks:
    - claude-sonnet: ["gpt-4o"]
    - gpt-4o: ["gpt-3.5-turbo"]
  context_window_fallbacks:
    - gpt-4o: ["gpt-3.5-turbo-16k"]
  content_policy_fallbacks:
    - gpt-4o: ["claude-sonnet"]

  # Cache
  cache: true
  cache_params:
    type: redis
    ttl: 600
    namespace: "litellm.caching"

  # Budgets (global)
  max_budget: 100 # USD cap
  budget_duration: 30d # auto-reset
  max_end_user_budget: 5 # per-user in /chat/completions
  max_internal_user_budget: 20
  internal_user_budget_duration: "1mo"

  # Key generation constraints
  upperbound_key_generate_params:
    max_budget: 100
    duration: "30d"
    tpm_limit: 1000
  default_key_generate_params:
    max_budget: 1.50
    models: ["gpt-3.5-turbo"]

  # Misc
  allowed_fails: 2
  turn_off_message_logging: false # redact prompt content from logs
```

---

## general_settings

Server-level.

```yaml
general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY # Bearer token for admin ops
  database_url: os.environ/DATABASE_URL # PostgreSQL
  salt_key: os.environ/LITELLM_SALT_KEY # encrypts stored provider keys

  database_connection_pool_limit: 15
  database_connection_timeout: 60

  alerting: ["slack", "pagerduty"]
  alerting_threshold: 300 # ms latency threshold for alerts
  alert_types:
    - "llm_exceptions"
    - "budget_alerts"
    - "db_exceptions"

  # Auth
  litellm_key_header_name: "X-Litellm-Key" # custom auth header
  enforced_params: ["user"] # require field in requests
  allow_client_side_credentials: false # reject requests passing api_key
  enable_jwt_auth: true # JWT via IDP
  use_x_forwarded_for: true # trust proxy for IP

  # MCP / stored models
  store_model_in_db: true
  supported_db_objects: ["mcp"]

  # Budget scheduler
  proxy_budget_rescheduler_min_time: 1
  proxy_budget_rescheduler_max_time: 1

  # Virtual key cache
  user_api_key_cache_ttl: 60

  # Secret manager (Enterprise)
  key_management_system: "aws_secret_manager"
  key_management_settings:
    store_virtual_keys: true
    prefix_for_stored_virtual_keys: "litellm/"
    access_mode: "read_and_write"

  # Rate limit token counting
  token_rate_limit_type: "total" # total | input | output

  # Custom auth
  custom_key_generate: custom_auth.custom_generate_key_fn
```

---

## credential_list

Centralize shared credentials across models.

```yaml
credential_list:
  - credential_name: default_azure
    credential_values:
      api_key: os.environ/AZURE_API_KEY
      api_base: os.environ/AZURE_API_BASE
      api_version: "2023-07-01-preview"
    credential_info:
      description: "Production EU Azure"
      custom_llm_provider: "azure"

model_list:
  - model_name: gpt-4o
    litellm_params:
      model: azure/gpt-4o
      litellm_credential_name: default_azure # reuse
```

---

## environment_variables

Set env vars for the proxy process.

```yaml
environment_variables:
  REDIS_HOST: redis.example.com
  REDIS_PORT: "6379"
  LANGFUSE_PUBLIC_KEY: os.environ/LANGFUSE_PUBLIC_KEY
  LANGFUSE_SECRET_KEY: os.environ/LANGFUSE_SECRET_KEY
  SLACK_WEBHOOK_URL: os.environ/SLACK_WEBHOOK_URL
```

Values propagate to callbacks and provider SDKs.

---

## Complete example

```yaml
model_list:
  - model_name: claude-sonnet
    litellm_params:
      model: anthropic/claude-sonnet-4-6
      api_key: os.environ/ANTHROPIC_API_KEY
      rpm: 200

  - model_name: gpt-4o
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY
      rpm: 500

  - model_name: voyage-embedding
    litellm_params:
      model: voyage/voyage-3
      api_key: os.environ/VOYAGE_API_KEY

  - model_name: ollama-local
    litellm_params:
      model: ollama/llama3
      api_base: http://ollama:11434

litellm_settings:
  drop_params: true
  num_retries: 3
  success_callback: ["langfuse", "prometheus"]
  failure_callback: ["sentry"]
  fallbacks:
    - claude-sonnet: ["gpt-4o"]
    - gpt-4o: ["claude-sonnet"]
  cache: true
  cache_params:
    type: redis
    ttl: 3600

router_settings:
  routing_strategy: simple-shuffle
  num_retries: 2
  cooldown_time: 30
  redis_host: os.environ/REDIS_HOST
  redis_password: os.environ/REDIS_PASSWORD

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  database_url: os.environ/DATABASE_URL
  alerting: ["slack"]
  database_connection_pool_limit: 15
```

## os.environ/ syntax

Anywhere in the config — resolves at load time from process env:

```yaml
api_key: os.environ/OPENAI_API_KEY # ✓
redis_password: os.environ/REDIS_PASS # ✓
```

Missing env var → startup error with variable name in logs.

## Provider prefixes (quick ref)

| Prefix         | Provider              |
| -------------- | --------------------- |
| `openai/`      | OpenAI                |
| `anthropic/`   | Anthropic             |
| `azure/`       | Azure OpenAI          |
| `bedrock/`     | AWS Bedrock           |
| `vertex_ai/`   | Google Vertex AI      |
| `gemini/`      | Google AI Studio      |
| `mistral/`     | Mistral AI            |
| `cohere/`      | Cohere                |
| `groq/`        | Groq                  |
| `voyage/`      | Voyage AI             |
| `ollama/`      | Ollama local          |
| `huggingface/` | HuggingFace inference |
| `openrouter/`  | OpenRouter            |

Full list (100+): skill `litellm-providers-models`.

## Source

docs.litellm.ai/docs/proxy/config_settings + configs — scraped 2026-04-14.
