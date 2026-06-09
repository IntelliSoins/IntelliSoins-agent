---
description: vLLM-MLX — référence API complète (CLI serve + toutes options, endpoints chat/completions/models/health/rerank/responses/metrics, structured output, vision, tool calling, async client, error handling). Sous-rule de ~/.claude/rules/vllm-mlx.md.
paths:
  - "**/*vllm*mlx*api*"
  - "**/*vllm-mlx*client*"
---

# vLLM-MLX API Reference

> Sous-rule de `~/.claude/rules/vllm-mlx.md`. Transféré du skill `intellisoins-mlx:vllm-mlx` (`references/api_reference.md`) le 2026-05-24.

Complete reference for vLLM-MLX server configuration and API endpoints.

## CLI Reference

### serve command

```bash
vllm-mlx serve <model> [options]
```

### All Options

| Option                   | Type  | Default        | Description                                                        |
| ------------------------ | ----- | -------------- | ------------------------------------------------------------------ |
| `model`                  | str   | required       | HuggingFace model ID or local path                                 |
| `--port`                 | int   | 8000           | Server port                                                        |
| `--host`                 | str   | 127.0.0.1      | Bind address (⚠️ v0.2.9 breaking soft: was `0.0.0.0`)              |
| `--api-key`              | str   | None           | API key for authentication                                         |
| `--continuous-batching`  | flag  | False          | Enable vLLM paged attention scheduler                              |
| `--max-num-seqs`         | int   | 256            | Maximum concurrent sequences (with batching)                       |
| `--cache-memory-percent` | float | 0.25           | GPU memory fraction for KV cache                                   |
| `--reasoning-parser`     | str   | None           | Parser for thinking extraction: `qwen3`, `deepseek_r1`             |
| `--max-model-len`        | int   | auto           | Maximum context length                                             |
| `--trust-remote-code`    | flag  | False          | Trust remote code in model repo (v0.2.9: explicit opt-in required) |
| `--ssd-cache-dir`        | str   | None           | Spill prefix cache to disk (long-context agents)                   |
| `--ssd-cache-max-gb`     | int   | None           | SSD cache size limit (GB)                                          |
| `--warm-prompts`         | str   | None           | Preload popular prefixes at startup (1.3-2.25× TTFT)               |
| `--prefill-step-size`    | int   | auto           | Prefill chunk size                                                 |
| `--served-model-name`    | str   | model basename | Override model name in API responses                               |
| `--metrics`              | flag  | False          | Enable Prometheus `/metrics` endpoint                              |

### Example Configurations

**High-throughput multi-user:**

```bash
vllm-mlx serve mlx-community/Qwen3-4B-8bit \
  --continuous-batching \
  --max-num-seqs 256 \
  --cache-memory-percent 0.20 \
  --port 8000
```

**Memory-constrained (16GB Mac):**

```bash
vllm-mlx serve mlx-community/Qwen3-0.6B-4bit \
  --cache-memory-percent 0.10 \
  --max-model-len 2048
```

**Reasoning model with thinking:**

```bash
vllm-mlx serve mlx-community/DeepSeek-R1-0528-Qwen3-8B-4bit \
  --reasoning-parser deepseek_r1 \
  --continuous-batching
```

**Long-context agent with SSD KV cache tiering (v0.2.9+):**

```bash
vllm-mlx serve mlx-community/Qwen3-8B-4bit \
  --continuous-batching \
  --ssd-cache-dir ~/.cache/vllm-mlx/kv \
  --ssd-cache-max-gb 50 \
  --warm-prompts prompts.txt
```

## API Endpoints

All endpoints follow OpenAI API specification.

### POST /v1/chat/completions

Chat completions with optional streaming.

**Request:**

```json
{
  "model": "default",
  "messages": [
    { "role": "system", "content": "You are helpful." },
    { "role": "user", "content": "Hello!" }
  ],
  "temperature": 0.7,
  "max_tokens": 1024,
  "stream": false
}
```

**Response:**

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "default",
  "choices": [
    {
      "index": 0,
      "message": { "role": "assistant", "content": "Hello!" },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 5,
    "total_tokens": 15
  }
}
```

### POST /v1/completions

Text completions (legacy endpoint).

**Request:**

```json
{
  "model": "default",
  "prompt": "Once upon a time",
  "max_tokens": 100,
  "temperature": 0.8
}
```

### GET /v1/models

List available models.

**Response:**

```json
{
  "data": [{ "id": "default", "object": "model", "owned_by": "local" }]
}
```

### GET /health

Health check endpoint.

### POST /v1/rerank (v0.2.9+)

BERT-based reranker with token-budget batching (#308). Useful for RAG pipelines.

**Request:**

```json
{
  "model": "default",
  "query": "What is MLX?",
  "documents": [
    "MLX is an array framework for Apple Silicon.",
    "TensorFlow is a deep learning library by Google.",
    "MLX supports unified memory on M-series chips."
  ]
}
```

**Response:**

```json
{
  "results": [
    { "index": 0, "relevance_score": 0.92 },
    { "index": 2, "relevance_score": 0.87 },
    { "index": 1, "relevance_score": 0.04 }
  ]
}
```

Serve a BERT classifier (e.g. `mlx-community/bge-reranker-base`) for this endpoint.

### POST /v1/responses (v0.2.9+)

OpenAI Responses API compatibility layer (#214). Mirrors the OpenAI Responses schema — see [OpenAI's official Responses API docs](https://platform.openai.com/docs/api-reference/responses) for the full request/response shape.

### GET /metrics (v0.2.9+)

Prometheus exposition format. Requires `--metrics` flag at server startup. Exposes request counts, latency histograms, queue depth, KV cache hit rate, GPU memory.

## Structured Output

Request JSON schema-constrained output (v0.2.9 uses `lm-format-enforcer` for JSON Schema constrained decoding, #362):

```python
response = client.chat.completions.create(
    model="default",
    messages=[{"role": "user", "content": "Generate a person"}],
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "person",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"}
                },
                "required": ["name", "age"]
            }
        }
    }
)
```

## Vision-Language API

Send images with messages:

```python
response = client.chat.completions.create(
    model="default",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "Describe this image"},
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/jpeg;base64,/9j/4AAQ..."
                }
            }
        ]
    }]
)
```

Supported image formats:

- Base64 data URLs: `data:image/jpeg;base64,...`
- Local file paths: `file:///path/to/image.jpg`
- HTTP URLs: `https://example.com/image.jpg`

## Tool Calling

Define and call tools:

```python
tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get weather for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
            },
            "required": ["location"]
        }
    }
}]

response = client.chat.completions.create(
    model="default",
    messages=[{"role": "user", "content": "What's the weather in Tokyo?"}],
    tools=tools,
    tool_choice="auto"
)

# Check for tool calls
if response.choices[0].message.tool_calls:
    tool_call = response.choices[0].message.tool_calls[0]
    print(f"Function: {tool_call.function.name}")
    print(f"Args: {tool_call.function.arguments}")
```

## Async Client Usage

```python
import asyncio
from openai import AsyncOpenAI

async def main():
    client = AsyncOpenAI(
        base_url="http://localhost:8000/v1",
        api_key="not-needed"
    )

    response = await client.chat.completions.create(
        model="default",
        messages=[{"role": "user", "content": "Hello!"}]
    )
    print(response.choices[0].message.content)

asyncio.run(main())
```

## Error Handling

Common HTTP status codes:

| Code | Meaning                         |
| ---- | ------------------------------- |
| 200  | Success                         |
| 400  | Invalid request parameters      |
| 401  | Invalid API key (if configured) |
| 404  | Model not found                 |
| 500  | Server error                    |
| 503  | Model loading / server busy     |

Handle errors gracefully:

```python
from openai import OpenAI, APIError, APIConnectionError

client = OpenAI(base_url="http://localhost:8000/v1", api_key="not-needed")

try:
    response = client.chat.completions.create(
        model="default",
        messages=[{"role": "user", "content": "Hello"}]
    )
except APIConnectionError:
    print("Server not running or unreachable")
except APIError as e:
    print(f"API error: {e.status_code} - {e.message}")
```
