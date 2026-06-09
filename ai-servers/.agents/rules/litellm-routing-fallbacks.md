---
paths:
  - "**/litellm/callbacks/**"
  - "**/litellm-*/fallback*"
  - "**/fallback_alert*"
  - "**/litellm*router*"
  - "**/cooldown*"
---

# LiteLLM Routing & Fallbacks

Core reliability layer. Works in both SDK (via `Router` class) and Proxy (via `router_settings` + `litellm_settings.fallbacks`).

## Routing strategies

| Strategy                   | Selection                          | Use case                                      |
| -------------------------- | ---------------------------------- | --------------------------------------------- |
| `simple-shuffle` (default) | Random weighted by rpm/tpm/weight  | Balanced multi-deployment                     |
| `least-busy`               | Fewest in-flight requests          | Spiky load                                    |
| `usage-based-routing`      | Lowest TPM this minute             | Strict rate-limit compliance (requires Redis) |
| `latency-based-routing`    | Lowest recent latency              | Perf-critical paths                           |
| `cost-based-routing`       | Lowest cost per token              | Cost-optimized                                |
| `custom`                   | Extend `CustomRoutingStrategyBase` | Business logic                                |

## Router class (Python SDK)

```python
from litellm import Router

model_list = [
    {
        "model_name": "gpt-4o",                  # user-facing alias
        "litellm_params": {
            "model": "azure/gpt-4o-east",
            "api_key": os.environ["AZURE_KEY_EAST"],
            "api_base": "https://east.openai.azure.com",
            "rpm": 500,
            "tpm": 100000,
        },
    },
    {
        "model_name": "gpt-4o",
        "litellm_params": {
            "model": "azure/gpt-4o-west",
            "api_key": os.environ["AZURE_KEY_WEST"],
            "api_base": "https://west.openai.azure.com",
            "rpm": 500,
            "tpm": 100000,
        },
    },
]

router = Router(
    model_list=model_list,
    routing_strategy="simple-shuffle",
    num_retries=3,
    retry_after=5,
    allowed_fails=1,
    cooldown_time=60,
    fallbacks=[{"gpt-4o": ["claude-sonnet"]}],
)

response = router.completion(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hi"}],
)
```

## Proxy (config.yaml)

```yaml
model_list:
  - model_name: gpt-4o
    litellm_params:
      model: azure/gpt-4o-east
      api_base: https://east.openai.azure.com
      rpm: 500
  - model_name: gpt-4o
    litellm_params:
      model: azure/gpt-4o-west
      api_base: https://west.openai.azure.com
      rpm: 500

router_settings:
  routing_strategy: simple-shuffle
  num_retries: 3
  cooldown_time: 60
  redis_host: redis.example.com
  redis_port: 6379
  enable_pre_call_check: true

litellm_settings:
  fallbacks:
    - gpt-4o: ["claude-sonnet"]
  context_window_fallbacks:
    - gpt-4o: ["gpt-4o-long"]
  content_policy_fallbacks:
    - gpt-4o: ["claude-sonnet"]
```

## Simple-shuffle (weighted)

```python
model_list = [
    {
        "model_name": "claude",
        "litellm_params": {"model": "anthropic/claude-sonnet-4-6", "weight": 9},
        # 90% traffic
    },
    {
        "model_name": "claude",
        "litellm_params": {"model": "bedrock/anthropic.claude-3-5-sonnet", "weight": 1},
        # 10% traffic
    },
]
router = Router(model_list=model_list, routing_strategy="simple-shuffle")
```

## Least-busy

```python
router = Router(model_list=model_list, routing_strategy="least-busy")
```

Tracks in-flight request counts per deployment. Picks lowest.

## Usage-based (TPM)

Requires Redis. Routes to deployment with lowest TPM consumption this minute:

```python
router = Router(
    model_list=model_list,
    redis_host=os.environ["REDIS_HOST"],
    redis_password=os.environ["REDIS_PASSWORD"],
    redis_port=os.environ["REDIS_PORT"],
    routing_strategy="usage-based-routing-v2",     # v2 faster
    enable_pre_call_checks=True,
)
```

## Latency-based

```python
router = Router(
    model_list=model_list,
    routing_strategy="latency-based-routing",
    enable_pre_call_check=True,
    routing_strategy_args={
        "ttl": 10,                          # rolling window (seconds)
        "lowest_latency_buffer": 0.5,       # 50% buffer to prevent overload
    },
)
```

## Cost-based

```python
model_list = [
    {
        "model_name": "cheap-or-smart",
        "litellm_params": {
            "model": "groq/llama3-8b-8192",
            "input_cost_per_token": 0.000000001,
            "output_cost_per_token": 0.00000001,
        },
    },
    {
        "model_name": "cheap-or-smart",
        "litellm_params": {
            "model": "openai/gpt-4",
            "input_cost_per_token": 0.00003,
            "output_cost_per_token": 0.00003,
        },
    },
]
router = Router(model_list=model_list, routing_strategy="cost-based-routing")
```

Picks Groq (10000x cheaper). Pricing from `litellm.model_cost` by default.

## Custom strategy

```python
from litellm.router import CustomRoutingStrategyBase

class BusinessHoursStrategy(CustomRoutingStrategyBase):
    async def async_get_available_deployment(
        self, model, messages=None, input=None,
        specific_deployment=False, request_kwargs=None,
    ):
        from datetime import datetime
        hour = datetime.utcnow().hour
        # Route to cheap model off-hours
        if 22 <= hour or hour < 6:
            return self.get_deployment_by_model("groq/llama3-8b-8192")
        return self.get_deployment_by_model("openai/gpt-4o")

    def get_available_deployment(self, *args, **kwargs):
        return asyncio.run(self.async_get_available_deployment(*args, **kwargs))

router.set_custom_routing_strategy(BusinessHoursStrategy())
```

## Priority-ordered deployments

Lower `order` = higher priority. Fallthrough on failure:

```yaml
model_list:
  - model_name: gpt-4
    litellm_params:
      model: azure/gpt-4-primary
      order: 1 # tried first
  - model_name: gpt-4
    litellm_params:
      model: azure/gpt-4-fallback
      order: 2 # used when order:1 fails
```

## Cooldowns

Temporarily remove failing deployments from rotation.

```yaml
router_settings:
  allowed_fails: 3 # N failures/min → cooldown
  cooldown_time: 30 # seconds
```

Per-deployment override:

```yaml
model_list:
  - model_name: flaky-backend
    litellm_params:
      model: predibase/llama-3-8b
      cooldown_time: 0 # disable cooldown for this one
```

### Policy by error type

```python
from litellm.router import RetryPolicy, AllowedFailsPolicy

retry_policy = RetryPolicy(
    ContentPolicyViolationErrorRetries=3,
    AuthenticationErrorRetries=0,
    TimeoutErrorRetries=2,
    RateLimitErrorRetries=3,
    BadRequestErrorRetries=0,
)

allowed_fails_policy = AllowedFailsPolicy(
    ContentPolicyViolationErrorAllowedFails=1000,
    RateLimitErrorAllowedFails=100,
)

router = Router(
    model_list=model_list,
    retry_policy=retry_policy,
    allowed_fails_policy=allowed_fails_policy,
)
```

## Retries

```python
router = Router(
    model_list=model_list,
    num_retries=3,
    retry_after=5,                      # minimum seconds before retry
)
```

Exponential backoff automatic for rate limit errors.

## Fallbacks — 3 types

### Model fallback (any failure)

```yaml
litellm_settings:
  fallbacks:
    - gpt-4o: ["claude-sonnet", "gpt-3.5-turbo"]
```

Triggered by any exception. Tried in order.

### Context window fallback

```yaml
litellm_settings:
  context_window_fallbacks:
    - gpt-4o: ["gpt-4o-128k", "claude-sonnet"]
```

Triggered only on `ContextWindowExceededError`.

### Content policy fallback

```yaml
litellm_settings:
  content_policy_fallbacks:
    - gpt-4o: ["claude-sonnet"]
```

Triggered on `ContentPolicyViolationError` (content filter blocked).

## Pre-call checks

Filter deployments before routing (context window, region):

```yaml
model_list:
  - model_name: gpt-3.5-turbo
    litellm_params:
      model: azure/gpt-35-turbo
      base_model: azure/gpt-35-turbo # for context window lookup
      region_name: eu # geo filter
router_settings:
  enable_pre_call_checks: true
```

Client can request `region_name`:

```python
response = router.completion(
    model="gpt-3.5-turbo",
    messages=[...],
    region_name="eu",
)
```

## Max parallel requests

Concurrent cap per deployment:

```yaml
model_list:
  - model_name: gpt-4
    litellm_params:
      model: azure/gpt-4
      max_parallel_requests: 10
```

Global default:

```python
router = Router(model_list=model_list, default_max_parallel_requests=20)
```

## Tag-based routing

Route based on request tags:

```python
router = Router(
    model_list=[
        {
            "model_name": "tiered-model",
            "litellm_params": {"model": "openai/gpt-4o"},
            "tags": ["paid"],
        },
        {
            "model_name": "tiered-model",
            "litellm_params": {"model": "groq/llama3-8b-8192"},
            "tags": ["free"],
        },
    ],
)

response = router.completion(
    model="tiered-model",
    messages=[...],
    tags=["free"],
)
```

Proxy header: `x-litellm-tags: free`.

## A/B testing (traffic mirroring)

Send traffic to a primary model and mirror to a test model (response from primary):

```yaml
router_settings:
  mirror_traffic_targets:
    - primary: gpt-4o
      mirror: claude-sonnet
      mirror_percentage: 10 # 10% of traffic mirrored
```

Mirror responses logged but not returned to client. Useful for evaluating new models safely.

## Caching shared across aliases

```python
router = Router(
    model_list=model_list,
    cache_responses=True,
    caching_groups=[("openai-gpt-3.5-turbo", "azure-gpt-3.5-turbo")],
)
```

Responses from either alias share cache.

## Alerting

```python
from litellm.types.router import AlertingConfig

router = Router(
    model_list=model_list,
    alerting_config=AlertingConfig(
        alerting_threshold=10,
        webhook_url="https://hooks.slack.com/services/...",
    ),
)
```

## Router endpoints

| Method                                                     | Purpose    |
| ---------------------------------------------------------- | ---------- |
| `router.completion()` / `router.acompletion()`             | Chat       |
| `router.embedding()` / `router.aembedding()`               | Embeddings |
| `router.text_completion()` / `router.atext_completion()`   | Legacy     |
| `router.image_generation()` / `router.aimage_generation()` | Images     |

## Debugging

```python
router = Router(
    model_list=model_list,
    set_verbose=True,
    debug_level="DEBUG",
)

import litellm
litellm.set_verbose = True               # global SDK verbose
```

Inspect routing decisions in logs:

```
litellm.Router: routing_strategy: simple-shuffle
litellm.Router: picked deployment_id: xyz-123 (azure/gpt-4o-east)
```

## IntelliSoins pattern

```yaml
model_list:
  # Primary: Anthropic (prod-trusted)
  - model_name: claude-sonnet
    litellm_params:
      model: anthropic/claude-sonnet-4-6
      api_key: os.environ/ANTHROPIC_API_KEY
      rpm: 200
      order: 1
  # Fallback: Bedrock (multi-region redundancy)
  - model_name: claude-sonnet
    litellm_params:
      model: bedrock/anthropic.claude-3-5-sonnet-v2
      aws_region_name: us-east-1
      rpm: 200
      order: 2

router_settings:
  routing_strategy: simple-shuffle
  num_retries: 3
  cooldown_time: 60
  redis_host: os.environ/REDIS_HOST

litellm_settings:
  fallbacks:
    - claude-sonnet: ["claude-haiku"] # degrade model
  context_window_fallbacks:
    - claude-sonnet: ["claude-opus"] # upgrade for long context
  content_policy_fallbacks:
    - claude-sonnet: ["gpt-4o"] # cross-provider for filter rejection
```

## Source

docs.litellm.ai/docs/routing + /docs/proxy/reliability — scraped 2026-04-14.
