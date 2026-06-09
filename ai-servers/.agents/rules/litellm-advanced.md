---
paths:
  - "**/litellm*custom*plugin*"
  - "**/litellm*secret*manager*"
  - "**/vault*litellm*"
  - "**/litellm.env.sops*"
---

# LiteLLM Advanced

Custom extensions, secret management, troubleshooting, and API reference pointers.

## Custom plugins

Three extension points — subclass provided base classes and register in `config.yaml`.

### CustomLogger (callbacks)

```python
# custom_logger.py
from litellm.integrations.custom_logger import CustomLogger
import litellm

class AuditLogger(CustomLogger):
    def log_pre_api_call(self, model, messages, kwargs):
        # Sync: runs before LLM call
        pass

    def log_post_api_call(self, kwargs, response_obj, start_time, end_time):
        # Sync: runs after LLM call (success or fail)
        pass

    async def async_log_pre_api_call(self, model, messages, kwargs):
        pass

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        cost = litellm.completion_cost(completion_response=response_obj)
        user_id = kwargs.get("user", "anonymous")
        await audit_db.insert({
            "user": user_id,
            "model": kwargs.get("model"),
            "cost": cost,
            "duration_ms": (end_time - start_time).total_seconds() * 1000,
        })

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        pass

    async def async_log_stream_event(self, kwargs, response_obj, start_time, end_time):
        # Called per streaming chunk
        pass

audit_logger_instance = AuditLogger()
```

```yaml
litellm_settings:
  callbacks: custom_logger.audit_logger_instance
```

### CustomGuardrail

```python
# custom_guardrail.py
from litellm.integrations.custom_guardrail import CustomGuardrail
from litellm._logging import verbose_logger

class MedicalAdviceValidator(CustomGuardrail):
    def __init__(self, guardrail_name: str, event_hook: str, **kwargs):
        super().__init__(guardrail_name=guardrail_name, event_hook=event_hook, **kwargs)

    async def async_pre_call_hook(
        self, user_api_key_dict, cache, data, call_type
    ):
        # Modify or reject request
        messages = data.get("messages", [])
        for msg in messages:
            content = str(msg.get("content", ""))
            if "prescribe" in content.lower():
                raise Exception("Prescription advice blocked")
        return data

    async def async_moderation_hook(
        self, data, user_api_key_dict, call_type
    ):
        # During-call check (parallel with LLM)
        pass

    async def async_post_call_success_hook(
        self, data, user_api_key_dict, response
    ):
        # Post-call: can modify response
        return response
```

```yaml
guardrails:
  - guardrail_name: "medical-advice-validator"
    litellm_params:
      guardrail: custom_guardrail.MedicalAdviceValidator
      mode: "pre_call"
```

### Custom auth

```python
# custom_auth.py
from litellm.proxy._types import UserAPIKeyAuth

async def user_api_key_auth(request, api_key: str) -> UserAPIKeyAuth:
    # Custom validation — e.g., call your IDP, check DB, verify HMAC
    user_info = await validate_with_your_system(api_key)
    if not user_info:
        raise Exception("Invalid key")
    return UserAPIKeyAuth(
        api_key=api_key,
        user_id=user_info["user_id"],
        team_id=user_info["team_id"],
        max_budget=user_info["max_budget"],
    )
```

```yaml
general_settings:
  custom_auth: custom_auth.user_api_key_auth
```

### Custom pricing

```python
# custom_pricing.py
def get_model_cost(model: str, messages, response_obj):
    # Custom cost logic
    total_tokens = response_obj.usage.total_tokens
    if "gpt-4o" in model:
        return total_tokens * 0.00001
    return 0
```

```yaml
litellm_settings:
  custom_cost_calculator: custom_pricing.get_model_cost
```

### Mount custom plugin dir

```bash
docker run -v /path/to/plugins:/app/custom_plugins ... litellm
```

And in `config.yaml`:

```yaml
litellm_settings:
  callbacks: custom_plugins.my_module.my_instance
```

## Secret Managers (Enterprise)

Supported:

1. AWS Key Management Service (KMS)
2. AWS Secrets Manager
3. Azure Key Vault
4. CyberArk Conjur
5. Google Secret Manager
6. Google KMS
7. HashiCorp Vault

### Config structure

```yaml
general_settings:
  key_management_system: "aws_secret_manager" # required
  key_management_settings:
    store_virtual_keys: true
    prefix_for_stored_virtual_keys: "litellm/"
    access_mode: "read_and_write" # read_only | write_only | read_and_write
    hosted_keys: ["litellm_master_key"]
    primary_secret_name: "litellm_secrets" # JSON secret w/ many kv pairs
```

### AWS Secrets Manager

```yaml
general_settings:
  key_management_system: "aws_secret_manager"
  key_management_settings:
    store_virtual_keys: true
    access_mode: "read_and_write"
    primary_secret_name: "prod/litellm"
```

Env (AWS SDK default chain):

```bash
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
# Or IAM role on EC2/ECS
```

LiteLLM reads:

```bash
aws secretsmanager get-secret-value --secret-id prod/litellm
# Returns JSON: {"OPENAI_API_KEY": "...", "ANTHROPIC_API_KEY": "...", ...}
```

Reference in config:

```yaml
model_list:
  - model_name: gpt-4o
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY # resolved from AWS Secrets Manager
```

### Azure Key Vault

```yaml
general_settings:
  key_management_system: "azure_key_vault"
  key_management_settings:
    primary_secret_name: "litellm-secrets"
```

Env:

```bash
AZURE_KEY_VAULT_URI="https://vault.vault.azure.net/"
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
```

### Google Secret Manager

```yaml
general_settings:
  key_management_system: "google_secret_manager"
  key_management_settings:
    primary_secret_name: "projects/my-proj/secrets/litellm/versions/latest"
```

Env: `GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json`.

### HashiCorp Vault

```yaml
general_settings:
  key_management_system: "hashicorp_vault"
  key_management_settings:
    primary_secret_name: "secret/data/litellm"
```

Env:

```bash
VAULT_ADDR=https://vault.example.com
VAULT_TOKEN=hvs.xxx
# Or Kubernetes auth, AppRole, etc.
```

### CyberArk Conjur

```yaml
general_settings:
  key_management_system: "conjur"
```

Env:

```bash
CONJUR_APPLIANCE_URL=...
CONJUR_ACCOUNT=...
CONJUR_AUTHN_LOGIN=...
CONJUR_AUTHN_API_KEY=...
```

### IntelliSoins: SOPS + age recommendation

Skill `intellisoins-infrastructure:secrets-management` uses SOPS + age for `.env` encryption. Combine:

- SOPS decrypts `.env` at boot → vars populated
- LiteLLM reads `os.environ/VAR_NAME` references
- No external secret manager needed for VPS deployment

Alternative: Vault side-car container decrypts into env at startup.

## API Swagger / All Endpoints

Proxy exposes full Swagger UI at:

```
http://localhost:4000/docs
```

Programmatic OpenAPI spec:

```bash
curl http://localhost:4000/openapi.json
```

Hosted reference: [litellm-api.up.railway.app](https://litellm-api.up.railway.app/)

### Key endpoint categories

| Path prefix                | Purpose                             |
| -------------------------- | ----------------------------------- |
| `/v1/chat/completions`     | OpenAI-compat chat                  |
| `/v1/completions`          | Legacy                              |
| `/v1/embeddings`           | Embeddings                          |
| `/v1/images`               | Image gen/edit                      |
| `/v1/audio/transcriptions` | STT                                 |
| `/v1/audio/speech`         | TTS                                 |
| `/v1/rerank`               | Reranking                           |
| `/v1/responses`            | New "responses" API (OpenAI-compat) |
| `/v1/models`               | List models                         |
| `/key/*`                   | Virtual key mgmt                    |
| `/user/*`                  | User mgmt                           |
| `/team/*`                  | Team mgmt                           |
| `/customer/*`              | End-user budgets                    |
| `/budget/*`                | Budget templates                    |
| `/guardrails/*`            | Guardrail mgmt                      |
| `/spend/*`                 | Audit logs                          |
| `/cache/*`                 | Cache ping/delete                   |
| `/health*`                 | Liveness/readiness                  |
| `/metrics`                 | Prometheus                          |
| `/ui/*`                    | Admin UI                            |
| `/docs`                    | Swagger UI                          |
| `/v1/agents`               | A2A agent registry                  |
| `/mcp/*`                   | MCP gateway                         |

## Making LLM requests — useful headers

| Header                                     | Purpose                        |
| ------------------------------------------ | ------------------------------ |
| `Authorization: Bearer sk-...`             | Virtual key (or master)        |
| `x-litellm-tags: prod,team-a`              | Tag-based routing / guardrails |
| `x-litellm-timeout: 30`                    | Override per-request timeout   |
| `x-litellm-enable-message-redaction: true` | Redact on this call            |
| `traceparent: 00-...`                      | OTEL trace context             |
| `x-goog-metadata: {}`                      | Pass-through                   |

Response headers:
| Header | Content |
|--------|---------|
| `x-litellm-call-id` | Unique call ID (for log correlation) |
| `x-litellm-cache-key` | Cache key if cached |
| `x-litellm-model-api-base` | Backend API endpoint used |
| `x-litellm-model-id` | Deployment ID chosen by router |
| `x-litellm-response-duration-ms` | Total latency |
| `x-litellm-key-remaining-requests-<model>` | Rate limit remaining |
| `x-litellm-key-remaining-tokens-<model>` | TPM remaining |

## Troubleshooting

### Startup issues

| Symptom                               | Cause                    | Fix                                                                  |
| ------------------------------------- | ------------------------ | -------------------------------------------------------------------- |
| `Could not connect to database`       | DATABASE_URL wrong       | Check `pg_isready -h <host>`                                         |
| `Could not decrypt api_key`           | LITELLM_SALT_KEY changed | Restore old salt, or truncate `LiteLLM_ModelTable` and re-add models |
| `Missing master_key`                  | Not in env or config     | Set `LITELLM_MASTER_KEY` or `general_settings.master_key`            |
| Port 4000 already in use              | Conflict                 | Use `--port 4001` or kill existing process                           |
| `No models in DB, no config provided` | Neither populated        | Add models to config.yaml OR via `/model/new` API                    |

### Runtime errors

| Error                      | Cause                     | Fix                                   |
| -------------------------- | ------------------------- | ------------------------------------- |
| `401 Authentication Error` | Wrong virtual key         | Check key prefix `sk-` and master key |
| `404 Model not found`      | `model_name` absent       | `GET /v1/models` to verify            |
| `429 Rate Limit Exceeded`  | TPM/RPM hit               | Increase limits or add deployment     |
| `400 BadRequestError`      | Bad params for provider   | Enable `drop_params: true`            |
| `Context window exceeded`  | Messages too long         | Add `context_window_fallbacks`        |
| `Spent budget exceeded`    | Key/user/team over budget | Increase / wait for reset             |
| `Cache ping failed`        | Redis down                | Check `REDIS_URL`, firewall           |

### Performance issues

| Symptom                     | Cause                            | Fix                                             |
| --------------------------- | -------------------------------- | ----------------------------------------------- |
| High latency (>5s for chat) | Single worker blocking           | Increase `--num_workers`                        |
| DB connection timeouts      | Pool exhausted                   | Raise `database_connection_pool_limit`          |
| Slow startup                | Model list loading               | Reduce number of initial models, use DB storage |
| Memory growth               | Message logs retained            | Enable `turn_off_message_logging`               |
| Prometheus scrape slow      | Too many high-cardinality labels | Disable per-user metrics                        |

### Debug commands

```bash
# Detailed logs
litellm --config config.yaml --detailed_debug

# Verbose SDK
export LITELLM_LOG=DEBUG
litellm --config config.yaml

# Single-request trace
curl http://localhost:4000/v1/chat/completions \
  -H "x-debug: true" \
  -d '{...}'

# Test config load
litellm --config config.yaml --dry_run
```

### Health endpoints

```bash
curl http://localhost:4000/health               # all models
curl http://localhost:4000/health/liveliness    # proxy alive
curl http://localhost:4000/health/readiness     # DB + Redis ready
curl http://localhost:4000/health/services      # callback status
curl http://localhost:4000/cache/ping           # cache alive
```

## Extras

### Load testing

```python
# load_test.py
import asyncio
from litellm import acompletion

async def call():
    await acompletion(
        model="openai/gpt-3.5-turbo",
        api_base="http://localhost:4000",
        api_key="sk-1234",
        messages=[{"role": "user", "content": "hi"}],
    )

async def main():
    tasks = [call() for _ in range(100)]
    await asyncio.gather(*tasks)

asyncio.run(main())
```

### Managed agents (Hosted)

docs.litellm.ai/docs/hosted — managed LiteLLM Cloud.

### Benchmarks

See docs.litellm.ai/docs/benchmarks for throughput / latency under load.

### Contributing

[github.com/BerriAI/litellm/blob/main/CONTRIBUTING.md](https://github.com/BerriAI/litellm/blob/main/CONTRIBUTING.md)

## Source

docs.litellm.ai/docs/proxy/custom_plugins + secret_manager + troubleshooting + extras — scraped 2026-04-14.
