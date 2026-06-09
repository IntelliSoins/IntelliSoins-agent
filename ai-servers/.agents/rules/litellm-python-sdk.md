---
paths:
  - "**/litellm/**/*.py"
  - "**/litellm-*/**/*.py"
  - "**/*litellm*.py"
---

# LiteLLM Python SDK

In-process Python library — OpenAI-compatible interface to 100+ providers. For production gateway with keys/budgets/logs, use the Proxy (skill `litellm-proxy-setup`).

## Install

```bash
pip install litellm
```

## Core function: completion()

```python
from litellm import completion
import os

os.environ["ANTHROPIC_API_KEY"] = "..."

response = completion(
    model="anthropic/claude-sonnet-4-6",
    messages=[{"role": "user", "content": "Hello"}],
    temperature=0.7,
    max_tokens=1000,
)
print(response.choices[0].message.content)
```

Provider determined by prefix: `openai/`, `anthropic/`, `bedrock/`, `vertex_ai/`, `azure/`, `gemini/`, `groq/`, `ollama/`, `mistral/`, `cohere/`, etc.

## Required / optional parameters

| Param                                    | Type       | Notes                                                                    |
| ---------------------------------------- | ---------- | ------------------------------------------------------------------------ |
| `model`                                  | str        | **Required** — with provider prefix                                      |
| `messages`                               | list       | **Required** — `{role, content}` dicts; content can be multimodal blocks |
| `temperature`                            | float 0-2  | Sampling randomness                                                      |
| `top_p`                                  | float      | Nucleus sampling threshold                                               |
| `max_tokens` / `max_completion_tokens`   | int        | Output cap                                                               |
| `n`                                      | int        | Number of completions                                                    |
| `stream`                                 | bool       | Streaming mode                                                           |
| `stream_options`                         | dict       | `{include_usage: True}` to get tokens in stream                          |
| `tools`                                  | list       | Function calling schemas                                                 |
| `tool_choice`                            | str/dict   | `auto`, `none`, `required`, or specific tool                             |
| `parallel_tool_calls`                    | bool       | Concurrent function calls                                                |
| `response_format`                        | dict       | `{type: "json_object"}` or schema                                        |
| `seed`                                   | int        | Deterministic sampling                                                   |
| `stop`                                   | list       | Up to 4 stop sequences                                                   |
| `logprobs` / `top_logprobs`              | bool / int | Token probabilities                                                      |
| `presence_penalty` / `frequency_penalty` | float      | Repetition control                                                       |
| `logit_bias`                             | dict       | Token probability modifiers                                              |
| `user`                                   | str        | End-user ID                                                              |
| `api_base` / `api_version` / `api_key`   | str        | Override provider endpoint                                               |
| `timeout`                                | int        | Default 600s                                                             |
| `num_retries`                            | int        | Auto-retry count                                                         |
| `fallbacks`                              | list       | Model fallback chain                                                     |
| `metadata`                               | dict       | Custom logging payload                                                   |

## Async (acompletion)

```python
from litellm import acompletion
import asyncio

async def main():
    response = await acompletion(
        model="openai/gpt-4o",
        messages=[{"role": "user", "content": "Hello"}],
    )
    print(response.choices[0].message.content)

asyncio.run(main())
```

## Streaming

```python
response = completion(
    model="openai/gpt-4o",
    messages=[{"role": "user", "content": "Tell a story"}],
    stream=True,
    stream_options={"include_usage": True},
)

for chunk in response:
    delta = chunk.choices[0].delta
    if delta.content:
        print(delta.content, end="", flush=True)
```

Async streaming: same with `async for chunk in await acompletion(...)`.

## Tool use

```python
tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get current weather",
        "parameters": {
            "type": "object",
            "properties": {"location": {"type": "string"}},
            "required": ["location"],
        },
    },
}]

response = completion(
    model="anthropic/claude-sonnet-4-6",
    messages=[{"role": "user", "content": "Weather in Paris?"}],
    tools=tools,
    tool_choice="auto",
)
```

Works identically across providers supporting function calling.

## Multimodal content

```python
messages = [{
    "role": "user",
    "content": [
        {"type": "text", "text": "Describe this image"},
        {"type": "image_url", "image_url": {"url": "https://example.com/img.jpg"}},
    ],
}]
```

Supported block types: `text`, `image_url`, `input_audio`, `video_url`, `file`, `document`. Provider support varies — LiteLLM drops unsupported fields when `drop_params=True`.

## Embeddings

```python
from litellm import embedding

response = embedding(
    model="voyage/voyage-3",
    input=["Some text to embed"],
)
vectors = response.data[0]["embedding"]
```

Async: `aembedding()`. Works with OpenAI, Voyage, Cohere, Bedrock, Vertex, Azure.

## Router (in-process load balancing / fallbacks)

```python
from litellm import Router

model_list = [
    {
        "model_name": "gpt-4o",
        "litellm_params": {
            "model": "azure/gpt-4o-east",
            "api_key": os.environ["AZURE_KEY_EAST"],
            "api_base": "https://east.openai.azure.com",
            "rpm": 500,
        },
    },
    {
        "model_name": "gpt-4o",
        "litellm_params": {
            "model": "azure/gpt-4o-west",
            "api_key": os.environ["AZURE_KEY_WEST"],
            "api_base": "https://west.openai.azure.com",
            "rpm": 500,
        },
    },
]

router = Router(
    model_list=model_list,
    routing_strategy="simple-shuffle",
    num_retries=3,
    fallbacks=[{"gpt-4o": ["claude-sonnet-4-6"]}],
)

response = router.completion(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hi"}],
)
```

Routing strategies: `simple-shuffle` (default, weighted by rpm/tpm/weight), `least-busy`, `usage-based-routing`, `latency-based-routing`, `cost-based-routing`. Detail: skill `litellm-routing-fallbacks`.

## Cost tracking

```python
from litellm import completion_cost

cost_usd = completion_cost(completion_response=response)
```

Pricing pulled from `litellm.model_cost` (embedded DB updated per release).

## Callbacks (logging)

```python
import litellm

litellm.success_callback = ["langfuse"]  # env LANGFUSE_PUBLIC_KEY + SECRET_KEY
litellm.failure_callback = ["sentry"]
```

Detail + custom classes: skill `litellm-logging-metrics`.

## Global settings

```python
import litellm

litellm.set_verbose = True          # Debug logs
litellm.drop_params = True          # Drop provider-unsupported params silently
litellm.num_retries = 3             # Default retries
litellm.request_timeout = 30        # Default timeout
litellm.api_key = "..."             # Fallback API key
```

## Exceptions

All provider errors map to OpenAI exception classes:

- `litellm.exceptions.AuthenticationError`
- `litellm.exceptions.RateLimitError`
- `litellm.exceptions.ContextWindowExceededError`
- `litellm.exceptions.ServiceUnavailableError`
- `litellm.exceptions.BadRequestError`
- `litellm.exceptions.Timeout`

Wrap calls in `try/except` with these to handle uniformly across providers.

## Cross-reference

- Providers table + model prefixes: skill `litellm-providers-models`
- Router deep dive: skill `litellm-routing-fallbacks`
- Production gateway (keys, budgets, audit): skill `litellm-proxy-setup`

## Source

docs.litellm.ai/docs/completion — scraped 2026-04-14.
