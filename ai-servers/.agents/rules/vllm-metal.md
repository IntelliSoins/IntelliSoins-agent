---
description: vLLM Metal — plugin hardware officiel vllm-project pour inférence vLLM sur Apple Silicon (MLX backend + compat engine/scheduler/API vLLM). Paged attention Metal kernels, STT Whisper/Qwen3-ASR, TurboQuant KV compression. Charge on-demand sur fichiers vllm-metal, variables VLLM_METAL_* ou servers.yaml.
paths:
  - "**/*vllm-metal*"
  - "**/*vllm_metal*"
  - "**/servers.yaml"
---

# vLLM Metal (rule on-demand)

> **Provenance** : transféré du skill `intellisoins-mlx:vllm-metal` (`SKILL.md` + `references/configuration.md` fusionnés) le 2026-05-24.
> **Distinct de** : `vllm-mlx` (waybarrios, serveur standalone), `vmlx` (Jinho Jang), `vllm-omni` (GPU Linux). vllm-metal = plugin officiel vllm-project dans le core vLLM. Voir aussi `~/.claude/rules/local-ai-stack.md`.

Official community-maintained hardware plugin enabling vLLM inference on Apple Silicon. Uses MLX as primary compute backend while maintaining full vLLM engine/scheduler/API compatibility.

**Version actuelle** : v0.2.0 (April 2026) — unified paged varlen Metal kernel default + STT + TurboQuant.
**Docs** : https://docs.vllm.ai/projects/vllm-metal/en/latest/

**Repo**: [vllm-project/vllm-metal](https://github.com/vllm-project/vllm-metal) (Apache 2.0)

## vs vllm-mlx

| Aspect          | vllm-metal (this)            | vllm-mlx               |
| --------------- | ---------------------------- | ---------------------- |
| Maintainer      | vllm-project (official)      | waybarrios (community) |
| Architecture    | Plugin into vLLM core        | Standalone server      |
| Backend         | MLX + PyTorch interop        | MLX natif              |
| Paged Attention | Metal kernels (experimental) | Via vLLM scheduler     |
| Install         | One-line script + venv       | pip install            |

## Installation

```bash
# Install (creates ~/.venv-vllm-metal)
curl -fsSL https://raw.githubusercontent.com/vllm-project/vllm-metal/main/install.sh | bash

# Activate
source ~/.venv-vllm-metal/bin/activate

# Update
rm -rf ~/.venv-vllm-metal && curl -fsSL https://raw.githubusercontent.com/vllm-project/vllm-metal/main/install.sh | bash

# Uninstall
rm -rf ~/.venv-vllm-metal
```

Requires: Apple Silicon Mac, Python 3. Installs vllm-metal plugin + vLLM core (latest compatible) + transformers >=5.0.0. Note : `install.sh` ne pin pas de version vLLM précise — toujours résolu vers la version compatible upstream au moment de l'install.

### Optional: Rust frontend (experimental, v0.2.0+)

```bash
curl -fsSL https://raw.githubusercontent.com/vllm-project/vllm-metal/main/install.sh | bash -s -- --with-vllm-rs
```

Installs `vllm-frontend-rs` (Rust drop-in pour vLLM serving layer). Requiert Rust toolchain (rustup.rs). Voir `docs/rust_frontend.md` upstream.

## Quick Start

```bash
source ~/.venv-vllm-metal/bin/activate

# Serve a model (OpenAI-compatible API)
vllm serve mlx-community/Qwen3-0.6B-8bit --port 8000

# Test
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"mlx-community/Qwen3-0.6B-8bit","messages":[{"role":"user","content":"Hello"}]}'
```

## Configuration

### Environment Variables

| Variable                           | Default | Description                                               |
| ---------------------------------- | ------- | --------------------------------------------------------- |
| `VLLM_METAL_MEMORY_FRACTION`       | `auto`  | Memory allocation. `auto` or numeric (0,1] for paged mode |
| `VLLM_METAL_USE_MLX`               | `1`     | Enable MLX compute (0=PyTorch fallback)                   |
| `VLLM_MLX_DEVICE`                  | `gpu`   | Device: `gpu` or `cpu`                                    |
| `VLLM_METAL_BLOCK_SIZE`            | `16`    | KV cache block size                                       |
| `VLLM_METAL_USE_PAGED_ATTENTION`   | `0`     | Enable experimental paged attention                       |
| `VLLM_METAL_DEBUG`                 | `0`     | Debug logging                                             |
| `VLLM_METAL_PREFIX_CACHE`          | unset   | Enable prefix caching for prompt reuse                    |
| `VLLM_METAL_PREFIX_CACHE_FRACTION` | `0.05`  | Prefix cache memory fraction (0,1]                        |

### Memory Modes

| Mode            | Config                                                 | Notes                           |
| --------------- | ------------------------------------------------------ | ------------------------------- |
| **MLX default** | `PAGED_ATTENTION=0`, `MEMORY_FRACTION=auto`            | Simple, stable                  |
| **Paged KV**    | `PAGED_ATTENTION=1`, `MEMORY_FRACTION=auto` or numeric | Experimental, higher throughput |

**v0.2.0 default** : unified paged varlen Metal kernel — **83× TTFT, 3.6× throughput vs v0.1.0** (release officielle April 2026). Other models may still have compatibility issues — bench avant prod.

## Architecture

```
vLLM Core (engine, scheduler, OpenAI API)
    |
Plugin Layer (MetalPlatform, MetalWorker, MetalModelRunner)
    |
Unified Backend (MLX primary + PyTorch interop)
    |
Metal GPU (Apple Silicon unified memory, zero-copy)
```

- Full vLLM compatibility: engine, scheduler, tokenizers, OpenAI API
- HuggingFace model loading via transformers >=5.0.0
- GQA (Grouped-Query Attention) support
- Paged attention kernels adapted from mistral.rs (MIT)

## Speech-to-Text (STT, v0.2.0+)

Support OpenAI-compatible STT via Whisper et Qwen3-ASR, native MLX sur Apple Silicon.

```bash
# Install STT extras (post install.sh)
source ~/.venv-vllm-metal/bin/activate
pip install 'vllm-metal[stt]'

# Optional: ffmpeg pour formats non-WAV (mp3, m4a, flac)
brew install ffmpeg

# Serve Whisper
vllm serve openai/whisper-small --port 8000

# Transcribe
curl -X POST http://localhost:8000/v1/audio/transcriptions -F "file=@recording.wav"
```

Modèles supportés : Whisper (tiny/base/small/medium/large + turbo), Qwen3-ASR.

## TurboQuant KV Cache Compression (v0.2.0+)

Walsh-Hadamard rotation + per-block quantization → **2.5×-5× compression** du KV cache avec quality loss minimal. Quantize/dequantize natif Apple Silicon via MLX + Metal kernel.

```bash
VLLM_METAL_USE_PAGED_ATTENTION=1 vllm serve meta-llama/Llama-3.2-1B-Instruct \
  --dtype bfloat16 \
  --max-model-len 32768 \
  --additional-config '{"turboquant": true, "k_quant": "q8_0", "v_quant": "q3_0"}'
```

Configuré via `--additional-config` JSON (pas de variable env séparée). **Requiert `VLLM_METAL_USE_PAGED_ATTENTION=1`**.

> Pour TurboQuant en dehors du plugin Metal (mlx-vlm, mlx-openai-server, mlx_lm), voir `~/.claude/rules/turboquant-mlx.md`.

### Quant types

| `k_quant`               | Bits | Notes                             |
| ----------------------- | ---- | --------------------------------- |
| `q8_0`, `int8`, `uint8` | 8    | Near-lossless                     |
| `q5_0`                  | 5    | Bon trade-off qualité/taille      |
| `q4_0`, `int4`, `uint4` | 4    | Config TurboQuant paper           |
| `int2`, `uint2`         | 2    | Aggressive, perte qualité notable |

`v_quant` : Lloyd-Max non-uniform quantization avec Walsh-Hadamard rotation, valeurs mappées vers centroïdes pré-calculés par bitwidth.

Voir `docs/turboquant.md` upstream pour détails.

## Limitations

- **Inference only** — no training or fine-tuning
- Paged attention experimental (rough edges beyond Qwen3-0.6B)
- Apple Silicon required (no Intel Mac)
- MLX path requires `MEMORY_FRACTION=auto`

## Troubleshooting

**Model not loading**: Ensure HuggingFace model is downloaded. Try `huggingface-cli download <model-id>`.

**OOM**: Use quantized models (`*-4bit`, `*-8bit`), reduce memory fraction, close GPU apps.

**Paged attention issues**: Disable with `VLLM_METAL_USE_PAGED_ATTENTION=0` and test with default MLX mode.

**venv conflicts**: Isolate from other MLX venvs (`mlx-openai`, `mlx-audio`). Do not mix.

---

# Configuration Reference (détail)

> Transféré de `references/configuration.md`.

## Memory Configuration Matrix

Valid combinations of `VLLM_METAL_USE_PAGED_ATTENTION` and `VLLM_METAL_MEMORY_FRACTION`:

| Paged Attention | Memory Fraction |                Result                |
| :-------------: | :-------------: | :----------------------------------: |
|   0 (default)   | auto (default)  |      MLX default path — stable       |
|        0        |     numeric     |     INVALID — MLX requires auto      |
|        1        |      auto       | Paged KV, defaults to 0.9 internally |
|        1        |  numeric (0,1]  |  Paged KV with explicit allocation   |

## Paged Attention (Experimental)

Enable for higher throughput on supported models:

```bash
export VLLM_METAL_USE_PAGED_ATTENTION=1
export VLLM_METAL_MEMORY_FRACTION=0.8  # or auto
vllm serve mlx-community/Qwen3-0.6B-8bit
```

Early benchmarks (Qwen3-0.6B):

- ~82x improvement in Time-To-First-Token
- ~3.75x throughput improvement

Caveats: other models may have compatibility issues. Test with default MLX mode first.

## Prefix Caching

Reuse computed KV cache for repeated prompt prefixes:

```bash
export VLLM_METAL_PREFIX_CACHE=1
export VLLM_METAL_PREFIX_CACHE_FRACTION=0.05  # 5% of memory
vllm serve <model>
```

Useful for: RAG with shared system prompts, repeated context, batch inference.

## ModelScope Support (China)

```bash
export VLLM_USE_MODELSCOPE=True
export VLLM_METAL_MODELSCOPE_CACHE=/path/to/local/models  # optional
vllm serve <model-id-from-modelscope>
```

## Performance Tuning

### Model Size vs Memory

| Model Size | Quantization | Estimated RAM | Recommended |
| :--------: | :----------: | :-----------: | :---------: |
|    0.6B    |    8-bit     |     ~2 GB     |  8GB+ Mac   |
|     3B     |    4-bit     |     ~4 GB     |  16GB+ Mac  |
|    7-8B    |    4-bit     |     ~8 GB     |  16GB+ Mac  |
|    14B     |    4-bit     |    ~12 GB     |  32GB+ Mac  |
|    30B     |    4-bit     |    ~20 GB     |  48GB+ Mac  |
|    70B     |    4-bit     |    ~40 GB     |  96GB+ Mac  |

### Tips

1. Start with default MLX mode (no paged attention) for stability
2. Use `mlx-community/` quantized models from HuggingFace
3. Monitor memory pressure via Activity Monitor
4. Close other GPU apps (browsers with WebGPU, games)
5. For multi-model serving, use separate ports and venvs

## Codebase Stats

- 218 commits, 694 stars, 73 forks, 16 contributors
- Python 69.4%, Metal 24.9%, C++ 2.2%, Rust 2.2%, Shell 1.3%
- Paged attention kernels from mistral.rs (MIT) via HuggingFace kernels-community

## OpenAI API Endpoints

Standard vLLM endpoints exposed:

| Endpoint               | Method | Description                            |
| ---------------------- | ------ | -------------------------------------- |
| `/v1/chat/completions` | POST   | Chat completions (streaming supported) |
| `/v1/completions`      | POST   | Text completions                       |
| `/v1/models`           | GET    | List loaded models                     |
| `/health`              | GET    | Health check                           |

Full vLLM CLI and API docs: [docs.vllm.ai](https://docs.vllm.ai)
