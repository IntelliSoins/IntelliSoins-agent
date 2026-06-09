---
description: vLLM-MLX (waybarrios) — serveur d'inférence OpenAI + Anthropic compatible sur Apple Silicon. LLM/VLM avec continuous batching, MCP tool calling, multimodal, /v1/rerank (BERT) et embeddings. 400+ tok/s natif MLX. Supporte Qwen3/3.5, Llama, Gemma 4, DeepSeek-R1. Charge on-demand sur fichiers vllm-mlx ou servers.yaml.
paths:
  - "**/*vllm-mlx*"
  - "**/*vllm_mlx*"
  - "**/servers.yaml"
---

# vLLM-MLX (rule on-demand)

> **Provenance** : transféré du skill `intellisoins-mlx:vllm-mlx` (`SKILL.md`) le 2026-05-24. Détail API + modèles → sous-rules `~/.claude/rules/vllm-mlx/`.
> **Distinct de** : `vmlx` (Jinho Jang), `vllm-metal` (plugin officiel vllm-project), `vllm-omni` (GPU Linux). vLLM-MLX = projet waybarrios, serveur standalone Apple Silicon. Voir aussi `~/.claude/rules/local-ai-stack.md`.

OpenAI **and Anthropic** compatible inference server for Apple Silicon (waybarrios/vllm-mlx). Run LLMs and vision-language models (Llama, Qwen, Qwen3.5, Gemma 4, LLaVA, DeepSeek-R1) with continuous batching, MCP tool calling, multimodal, BERT reranking and embeddings. Native MLX backend achieves 400+ tokens/second. Current version: **v0.3.0** (2026-05-09, stable) — pre-release **v0.4.0rc1** (2026-05-21) available.

## Installation

```bash
# uv (recommended)
uv tool install git+https://github.com/waybarrios/vllm-mlx.git

# pip
pip install git+https://github.com/waybarrios/vllm-mlx.git

# development
git clone https://github.com/waybarrios/vllm-mlx.git && cd vllm-mlx && pip install -e .
```

## Quick Start

### Start a Server

```bash
# Basic server
vllm-mlx serve mlx-community/Llama-3.2-3B-Instruct-4bit --port 8000

# With continuous batching (multi-user)
vllm-mlx serve mlx-community/Qwen3-0.6B-8bit --continuous-batching

# With reasoning model support
vllm-mlx serve mlx-community/DeepSeek-R1-0528-Qwen3-8B-4bit --reasoning-parser deepseek_r1
```

### Connect with OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="not-needed"  # Local development
)

response = client.chat.completions.create(
    model="default",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
```

### Streaming

```python
stream = client.chat.completions.create(
    model="default",
    messages=[{"role": "user", "content": "Write a haiku"}],
    stream=True
)
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

### Connect with Anthropic SDK

Since v0.2.8, vllm-mlx exposes the Anthropic Messages API on the same port via `ThinkRouter`. Point the SDK at localhost:

```python
import anthropic

client = anthropic.Anthropic(
    base_url="http://localhost:8000",
    api_key="local"
)

message = client.messages.create(
    model="default",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello!"}]
)
```

Anthropic thinking content blocks are routed through `ThinkRouter` — reasoning tokens from Qwen3/DeepSeek-R1 surface as native `thinking` blocks in the Anthropic response format. Works natively with Claude Code as a local backend.

## Server Configuration

### CLI Options

| Option                   | Description                                                                 | Default               |
| ------------------------ | --------------------------------------------------------------------------- | --------------------- |
| `--port`                 | Server port                                                                 | 8000                  |
| `--host`                 | Bind address (⚠️ v0.2.9 breaking soft: was `0.0.0.0`)                       | localhost (127.0.0.1) |
| `--api-key`              | Authentication token                                                        | None                  |
| `--continuous-batching`  | Enable vLLM scheduler                                                       | False                 |
| `--max-num-seqs`         | Max concurrent sequences                                                    | 256                   |
| `--reasoning-parser`     | Extract thinking (`qwen3`, `deepseek_r1`) — O(1) state machine since v0.2.8 | None                  |
| `--tool-call-parser`     | Tool call format (`qwen`, `gemma4`, `minimax`, `harmony`, `deepseek_r1`)    | Auto                  |
| `--cache-memory-percent` | GPU memory for KV cache                                                     | 0.25                  |
| `--ssd-cache-dir`        | Spill prefix cache to disk (long-context agents)                            | None                  |
| `--ssd-cache-max-gb`     | SSD cache size limit (GB)                                                   | None                  |
| `--warm-prompts`         | Preload popular prefixes at startup (1.3-2.25× TTFT)                        | None                  |
| `--prefill-step-size`    | Prefill chunk size                                                          | auto                  |
| `--served-model-name`    | Override model name in API responses                                        | model basename        |
| `--metrics`              | Enable Prometheus `/metrics` endpoint                                       | False                 |

### Sampling Parameters (v0.2.8+)

Full sampling control via request payload:

| Param                | Description                   |
| -------------------- | ----------------------------- |
| `temperature`        | Randomness                    |
| `top_p`              | Nucleus sampling              |
| `top_k`              | Top-K sampling                |
| `min_p`              | Minimum probability threshold |
| `presence_penalty`   | Penalize token presence       |
| `repetition_penalty` | Penalize token repetition     |

Supported for both dense and MLLM continuous batching paths.

### Continuous Batching

Enables high-throughput multi-user serving with vLLM's paged attention scheduler:

```bash
vllm-mlx serve mlx-community/Qwen3-4B-8bit \
  --continuous-batching \
  --max-num-seqs 256 \
  --cache-memory-percent 0.15
```

Performance with continuous batching:

- 2-3.4x aggregate throughput at 16 concurrent requests
- Up to 4.3x speedup at 16 concurrent users
- Paged KV cache with prefix sharing for efficiency

## Multimodal Models

### Vision-Language Models

vLLM-MLX supports vision-language models via mlx-vlm:

```bash
# Start VLM server
vllm-mlx serve mlx-community/Qwen2-VL-2B-Instruct-4bit
```

```python
response = client.chat.completions.create(
    model="default",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "What's in this image?"},
            {"type": "image_url", "image_url": {"url": "file:///path/to/image.jpg"}}
        ]
    }]
)
```

Supported VLMs:

- Qwen2-VL, Qwen3-VL, **Qwen3.5-VL** (v0.2.8, hybrid model batching)
- **Gemma 4 multimodal** (v0.2.8, BatchKVCache + RotatingKVCache)
- Gemma 3 (auto-detected as MLLM)
- LLaVA variants

### Content-Based Prefix Caching

For repeated image/video queries, vLLM-MLX uses content hashing to eliminate redundant vision encoding:

- **28x speedup** on repeated image queries
- **24.7x speedup** on video analysis
- Reduces latency from 21.7s to 0.78s on cached queries

### Audio Models (Optional)

TTS and STT via mlx-audio integration:

| Model      | Languages       | Use Case               |
| ---------- | --------------- | ---------------------- |
| Kokoro     | 8               | Multi-language TTS     |
| Chatterbox | 15+             | Wide language coverage |
| VibeVoice  | English         | High-quality English   |
| VoxCPM     | Chinese/English | Bilingual              |
| Whisper    | Many            | Speech-to-text         |

## Reasoning Models

Extract thinking from reasoning models:

```bash
# Qwen3 with thinking extraction
vllm-mlx serve mlx-community/Qwen3-4B-8bit --reasoning-parser qwen3

# DeepSeek-R1
vllm-mlx serve mlx-community/DeepSeek-R1-0528-Qwen3-8B-4bit --reasoning-parser deepseek_r1
```

The reasoning parser extracts `<think>...</think>` blocks from model output.

## Tool Calling

### Tool Call Parsers (v0.2.8)

Auto-detected per model, or set explicitly with `--tool-call-parser`:

| Parser        | Models                   | Format                                              |
| ------------- | ------------------------ | --------------------------------------------------- |
| `qwen`        | Qwen2.5, Qwen3, Qwen3.5  | `<tool_call>` XML + `<function=name>` format (#281) |
| `gemma4`      | Gemma 4 (#269)           | Gemma 4 native                                      |
| `minimax`     | MiniMax (#231)           | MiniMax native                                      |
| `harmony`     | GPT-OSS / Harmony (#284) | Exposed in serve CLI                                |
| `deepseek_r1` | DeepSeek-R1              | Native R1 format                                    |

### MCP Tool Calling

vLLM-MLX integrates with Model Context Protocol for tool use:

```python
response = client.chat.completions.create(
    model="default",
    messages=[{"role": "user", "content": "What's the weather in Paris?"}],
    tools=[{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"]
            }
        }
    }]
)
```

## Performance Benchmarks

On Apple M4 Max (128GB):

| Model         | Tokens/sec | Notes            |
| ------------- | ---------- | ---------------- |
| Qwen3-0.6B    | 402-525    | Fastest          |
| Llama-3.2-1B  | 464        | Good balance     |
| Qwen3-4B-8bit | 180-220    | Mid-size         |
| Whisper-tiny  | 197x RTF   | Real-time factor |

21-87% higher throughput than llama.cpp across model sizes.

Reference benchmark v0.2.8 (Llama-3.2-1B-Instruct-4bit, mlx-lm 0.31.2): 402 tok/s, 436 tok/s throughput aggregate sur 10 prompts parallèles (2.38s total).

## What's New in v0.3.0 (2026-05-09)

- **Registry-backed multi-model serving**: swap de modèle par requête depuis un registry, sans relancer le serveur
- **Chunked prefill MLLM non-bloquant**: prefill multimodal découpé pour ne pas bloquer le scheduler de batching
- **Audio Gemma 4 en chat**: entrée audio supportée dans `chat()` pour les modèles Gemma 4
- **`--max-kv-size`** flag: cap explicite de la taille du KV cache
- **Annulation de requête + timeout streaming**: client cancel propre et timeout sur les flux SSE

### Pre-release v0.4.0rc1 (2026-05-21)

- **MTP Gemma 4** (multi-token prediction) via drafter MLLM
- **KV cache system-prompt** étendu au streaming LLM (prefix partagé persiste sur les réponses streamées)

See [GitHub releases](https://github.com/waybarrios/vllm-mlx/releases/tag/v0.3.0) for full changelog.

<citation>https://api.github.com/repos/waybarrios/vllm-mlx/releases — consulté 2026-05-29, release 2026-05-09</citation>

### Previously in v0.2.9 (2026-04-22)

- **Security hardening wave**: bind localhost par défaut, `trust_remote_code` opt-in, MCP sandbox `/execute`, SSRF block, path traversal bloqué, cap `max_tokens`, logs sanitisés (#324-#345)
- **`/v1/rerank`** (MLX BERT classifier, #308), **`/v1/responses`** OpenAI-compatible (#214), **Prometheus `/metrics`** (#314)
- **SSD KV cache tiering** (async promote/spill, SQLite index, `--ssd-cache-dir`/`--ssd-cache-max-gb`, #309) + **`--warm-prompts`** cold-start TTFT 1.3-2.25× (#373)
- **JSON Schema constrained decoding** via `lm-format-enforcer` (#362), **`bench-serve` CLI**, **Audio URL** in `chat()`, per-request SpecPrefill (#265), reasoning preserved non-streaming tool calls (#287, #315)

### Previously in v0.2.8 (2026-04-12)

- **Anthropic Messages API** via ThinkRouter (thinking content blocks)
- **Gemma 4** multimodal + tool call parser (#268, #269) and **Qwen3.5** hybrid batching (#160)
- **New tool parsers**: MiniMax (#231), Harmony (#284), Qwen `<function=name>` (#281)
- **Full sampling params** + reasoning parser as O(1) state machine (#213, #234)

## Benchmarking

`vllm-mlx bench-serve` runs end-to-end load benchmarks against a running server with SSE timing, sweeps, and hardware fingerprint output:

```bash
vllm-mlx bench-serve --base-url http://localhost:8000 --concurrency 1,4,16 --output table
```

## Security defaults (v0.2.9+)

- Server binds to `127.0.0.1` by default — pass `--host 0.0.0.0` explicitly to expose on the network
- `trust_remote_code` requires explicit opt-in flag (`--trust-remote-code`)
- MCP execute endpoint sandboxed; high-risk tools blocked by default
- Remote media fetches: SSRF protection enabled (private IPs, link-local, metadata endpoints blocked)
- Local file paths in multimodal input: path traversal blocked
- Logs and error details sanitized (no leaked tokens, paths, or request bodies)

## Troubleshooting

**Model not found**: Download first with `huggingface-cli download <model-id>`.

**Out of memory**: Use quantized models (`*-4bit`, `*-8bit`), reduce `--cache-memory-percent`, or close other GPU apps.

**Slow first request**: Expected - model loads on startup. Subsequent requests are fast.

**Port in use**: Change with `--port <number>`.

**Dependency conflicts**: Install in isolated venv:

```bash
python -m venv ~/.venvs/vllm-mlx
source ~/.venvs/vllm-mlx/bin/activate
pip install git+https://github.com/waybarrios/vllm-mlx.git
```

## Advanced Configuration

- Référence API complète, structured output, options avancées → `~/.claude/rules/vllm-mlx/api-reference.md`
- Modèles recommandés par cas d'usage et hardware → `~/.claude/rules/vllm-mlx/model-recommendations.md`
