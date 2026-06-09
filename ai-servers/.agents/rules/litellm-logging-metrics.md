---
paths:
  - "**/litellm/callbacks/**"
  - "**/trace_logger*"
  - "**/litellm*observability*"
  - "**/langfuse*"
  - "**/prometheus*litellm*"
  - "**/otel*litellm*"
---

# LiteLLM Logging & Observability

Multi-destination logging via callbacks. Each callback hooks into success/failure events.

## Supported callbacks (partial list)

### Observability platforms

`langfuse`, `langsmith`, `arize`, `langtrace`, `mlflow`, `helicone`, `lunary`, `athina`, `galileo`, `deepeval`, `phoenix`

### Tracing / APM

`otel` (OpenTelemetry: console, HTTP, gRPC), `datadog`, `sentry`

### Cloud storage

`s3_v2`, `gcs_bucket`, `azure_blob`, `aws_sqs`, `dynamodb`

### Messaging / alerts

`slack`, `pagerduty`, `email`

### Metrics

`prometheus` — exposes `/metrics` endpoint

### Custom

Python class extending `CustomLogger`

## Enable callbacks

```yaml
litellm_settings:
  success_callback: ["langfuse", "prometheus"]
  failure_callback: ["sentry", "slack"]
  callbacks: ["otel"] # both success + failure
```

## Langfuse

```yaml
model_list:
  - model_name: gpt-3.5-turbo
    litellm_params:
      model: gpt-3.5-turbo
      api_key: os.environ/OPENAI_API_KEY

litellm_settings:
  success_callback: ["langfuse"]
```

Env:

```bash
LANGFUSE_PUBLIC_KEY=pk_...
LANGFUSE_SECRET_KEY=sk_...
LANGFUSE_HOST=https://cloud.langfuse.com       # or self-hosted URL
```

Metadata injection (per request):

```bash
curl 'http://0.0.0.0:4000/chat/completions' \
  -H 'Authorization: Bearer $LITELLM_MASTER_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "what llm are you"}],
    "metadata": {
      "generation_name": "ishaan-test",
      "trace_id": "trace-id22",
      "trace_user_id": "user-id2",
      "session_id": "session-001",
      "tags": ["experiment-a"]
    }
  }'
```

Metadata maps to Langfuse trace/generation fields automatically.

## OpenTelemetry

### Console exporter (dev)

```bash
export OTEL_EXPORTER="console"
```

```yaml
litellm_settings:
  callbacks: ["otel"]
```

### HTTP (Honeycomb, Grafana Cloud, self-hosted Tempo)

```bash
export OTEL_EXPORTER="otlp_http"
export OTEL_ENDPOINT="https://api.honeycomb.io/v1/traces"
export OTEL_HEADERS="x-honeycomb-team=<api-key>"
```

### gRPC

```bash
export OTEL_EXPORTER="otlp_grpc"
export OTEL_ENDPOINT="http://tempo:4317"
```

### Context propagation

Pass `traceparent` header on request — LiteLLM joins the trace:

```
traceparent: 00-80e1afed08e019fc1110464cfa66635c-7a085853722dc6d2-01
```

Useful for connecting LLM spans to upstream app spans.

## Prometheus

```yaml
litellm_settings:
  callbacks: ["prometheus"]
```

Scrape endpoint: `GET /metrics`

Exposed metrics (sample):

- `litellm_requests_total{model, status}`
- `litellm_tokens_total{model, token_type}` (prompt, completion)
- `litellm_spend_total{model, team, user}`
- `litellm_llm_api_latency_seconds{model}` (histogram)
- `litellm_cache_hit_total`
- `litellm_fallback_total{from_model, to_model}`
- `litellm_deployment_failure_responses_total{litellm_model_name, api_base}`

### prometheus.yml

```yaml
global:
  scrape_interval: 15s
scrape_configs:
  - job_name: "litellm"
    static_configs:
      - targets: ["litellm:4000"]
```

### Grafana dashboards

Official dashboard: [grafana.com/dashboards/22042](https://grafana.com/dashboards/22042). IntelliSoins: voir skill `intellisoins-infrastructure:grafana-dashboards`.

## S3 / GCS / Azure Blob / SQS

### S3

```yaml
litellm_settings:
  success_callback: ["s3_v2"]
  s3_callback_params:
    s3_bucket_name: logs-bucket-litellm
    s3_region_name: us-west-2
    s3_aws_access_key_id: os.environ/AWS_ACCESS_KEY_ID
    s3_aws_secret_access_key: os.environ/AWS_SECRET_ACCESS_KEY
    s3_path: my-test-path
    s3_use_team_prefix: true # prefix with team_id
    s3_use_key_prefix: true # prefix with key_name
```

### GCS

```yaml
litellm_settings:
  callbacks: ["gcs_bucket"]
```

Env: `GCS_BUCKET_NAME`, `GCS_PATH_SERVICE_ACCOUNT`.

### AWS SQS

```yaml
litellm_settings:
  callbacks: ["aws_sqs"]
  aws_sqs_callback_params:
    sqs_queue_url: https://sqs.us-west-2.amazonaws.com/123456789012/queue
    sqs_region_name: us-west-2
    sqs_strip_base64_files: false
```

## Datadog

```yaml
litellm_settings:
  callbacks: ["datadog"]
```

Env: `DD_API_KEY`, `DD_SITE`, `DD_ENV`, `DD_SERVICE`.

## Sentry

```bash
export SENTRY_DSN="https://xxx@sentry.io/yyy"
export SENTRY_API_SAMPLE_RATE="1.0"
export SENTRY_ENVIRONMENT="production"
```

```yaml
litellm_settings:
  failure_callback: ["sentry"]
```

## MLflow

```yaml
litellm_settings:
  success_callback: ["mlflow"]
```

Env: `MLFLOW_TRACKING_URI`, `MLFLOW_EXPERIMENT_NAME`.

## Slack alerts

```yaml
general_settings:
  alerting: ["slack"]
  alerting_threshold: 300 # ms — slow-call alert
  alert_types:
    - llm_exceptions
    - llm_too_slow
    - budget_alerts
    - db_exceptions
    - daily_reports
    - outage_alerts
  alert_to_webhook_url:
    budget_alerts: "https://hooks.slack.com/services/A/B/C"
    llm_exceptions: "https://hooks.slack.com/services/X/Y/Z"
```

Env: `SLACK_WEBHOOK_URL`.

## PagerDuty

```yaml
general_settings:
  alerting: ["pagerduty"]
  pagerduty_alerting_args:
    failure_threshold: 1 # pages after N failures
    failure_threshold_window_seconds: 60
```

Env: `PAGERDUTY_API_KEY`.

## LiteLLM Call ID

Every request gets a unique ID for cross-system correlation:

Response header:

```
x-litellm-call-id: b980db26-9512-45cc-b1da-c511a363b83f
```

Use in Langfuse metadata (`trace_id`) or Sentry tags to stitch logs together.

## Message redaction

### Global

```yaml
litellm_settings:
  success_callback: ["langfuse"]
  turn_off_message_logging: true # redact content in all logs
```

### Per-request

```bash
curl http://0.0.0.0:4000/v1/chat/completions \
  -H 'x-litellm-enable-message-redaction: true' \
  -d '{...}'
```

Sensitive data (patient info) never leaves the proxy process.

## Disable logging per request

```bash
curl http://0.0.0.0:4000/chat/completions \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [...],
    "no-log": true
  }'
```

Useful for testing / debugging without polluting metrics.

## Custom callback class

```python
# custom_callbacks.py
from litellm.integrations.custom_logger import CustomLogger
import litellm

class MyCustomHandler(CustomLogger):
    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        model = kwargs.get("model")
        messages = kwargs.get("messages")
        cost = litellm.completion_cost(completion_response=response_obj)
        # Send to your internal system
        await send_to_internal_api({
            "model": model,
            "cost": cost,
            "duration_ms": (end_time - start_time).total_seconds() * 1000,
        })

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        # Handle failures
        pass

proxy_handler_instance = MyCustomHandler()
```

```yaml
litellm_settings:
  callbacks: custom_callbacks.proxy_handler_instance
```

## StandardLoggingPayload

All callbacks receive a normalized payload:

```python
{
  "id": "chat-xyz",
  "call_type": "acompletion",
  "api_key": "sk-...xyz",               # hashed
  "model": "gpt-4o",
  "custom_llm_provider": "openai",
  "response_cost": 0.0023,
  "total_tokens": 150,
  "prompt_tokens": 100,
  "completion_tokens": 50,
  "start_time": "2026-04-14T...",
  "end_time": "...",
  "response_time": 1.234,
  "messages": [...],
  "response": {...},
  "metadata": {...},                    # user-provided + computed
  "cache_hit": false,
  "status": "success",
  "saved_cache_cost": 0.0,
  "error": null,
}
```

Full spec: [docs.litellm.ai/docs/proxy/logging_spec](https://docs.litellm.ai/docs/proxy/logging_spec).

## Daily reports

```yaml
general_settings:
  alerting: ["slack"]
  alert_types: ["daily_reports"]
  report_frequency: "daily"
```

Fires once/day with:

- Total spend
- Top 10 users/teams by spend
- Exceptions count
- Top models by usage

## JSON logs

```yaml
litellm_settings:
  json_logs: true
```

Process stdout becomes machine-parseable. Good for stacks using Loki/ELK.

## Debug mode

```bash
litellm --config config.yaml --detailed_debug
```

Or in config:

```yaml
litellm_settings:
  set_verbose: true
```

## IntelliSoins observability stack

### Recommended setup

```yaml
litellm_settings:
  success_callback: ["langfuse", "prometheus"]
  failure_callback: ["sentry", "slack"]
  callbacks: ["otel"]
  turn_off_message_logging: true # Loi 25 — no PHI in logs
  json_logs: true

general_settings:
  alerting: ["slack"]
  alert_types:
    - llm_exceptions
    - budget_alerts
    - daily_reports
  alert_to_webhook_url:
    budget_alerts: "https://hooks.slack.com/.../litellm-budget"
    llm_exceptions: "https://hooks.slack.com/.../litellm-errors"
```

### Env (vault via SOPS)

```bash
LANGFUSE_HOST=https://langfuse.intellisoins.ca     # self-host VPS
LANGFUSE_PUBLIC_KEY=pk_...
LANGFUSE_SECRET_KEY=sk_...
OTEL_EXPORTER=otlp_http
OTEL_ENDPOINT=http://tempo:4318/v1/traces
SENTRY_DSN=https://xxx@sentry.intellisoins.ca/yyy
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
```

### Integration existing stack

- Grafana: `intellisoins-infrastructure:grafana-dashboards` skill
- Prometheus: scraping job à ajouter dans `docker-compose.vps.yml`
- Traefik logs: déjà Loki-compatible

## Source

docs.litellm.ai/docs/proxy/logging + callbacks — scraped 2026-04-14.
