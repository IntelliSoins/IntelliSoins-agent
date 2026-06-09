---
description: vLLM-MLX — modèles MLX recommandés par cas d'usage et hardware (8/16/32/64 GB Mac), par tâche (chat/code/reasoning/vision/multi-user), formats de quantization, téléchargement. Sous-rule de ~/.claude/rules/vllm-mlx.md.
paths:
  - "**/*vllm*mlx*model*"
  - "**/*vllm-mlx*recommend*"
---

# vLLM-MLX Model Recommendations

> Sous-rule de `~/.claude/rules/vllm-mlx.md`. Transféré du skill `intellisoins-mlx:vllm-mlx` (`references/model_recommendations.md`) le 2026-05-24.

Recommended MLX models organized by use case and hardware requirements.

## Quick Reference

| Use Case  | Model                                        | Memory | Speed      |
| --------- | -------------------------------------------- | ------ | ---------- |
| Fast chat | mlx-community/Qwen3-0.6B-8bit                | ~2GB   | 400+ tok/s |
| Balanced  | mlx-community/Llama-3.2-3B-Instruct-4bit     | ~4GB   | 200+ tok/s |
| Quality   | mlx-community/Qwen3-8B-4bit                  | ~6GB   | 100+ tok/s |
| Reasoning | mlx-community/DeepSeek-R1-0528-Qwen3-8B-4bit | ~6GB   | 80+ tok/s  |
| Vision    | mlx-community/Qwen2-VL-2B-Instruct-4bit      | ~4GB   | varies     |

## By Hardware

### 8GB Mac (M1/M2 base)

Best options for memory-constrained systems:

```bash
# Fastest
vllm-mlx serve mlx-community/Qwen3-0.6B-4bit --cache-memory-percent 0.10

# Better quality
vllm-mlx serve mlx-community/Llama-3.2-1B-Instruct-4bit --cache-memory-percent 0.10

# Vision (tight fit)
vllm-mlx serve mlx-community/Qwen2-VL-2B-Instruct-4bit --cache-memory-percent 0.08
```

### 16GB Mac (M1/M2 Pro, M3)

Good balance of quality and speed:

```bash
# Recommended general use
vllm-mlx serve mlx-community/Llama-3.2-3B-Instruct-4bit

# Higher quality
vllm-mlx serve mlx-community/Qwen3-4B-8bit

# Vision-language
vllm-mlx serve mlx-community/Qwen2-VL-7B-Instruct-4bit --cache-memory-percent 0.15
```

### 32GB+ Mac (M2 Max, M3 Max, M4 Max)

Full capability models:

```bash
# Best reasoning
vllm-mlx serve mlx-community/DeepSeek-R1-0528-Qwen3-8B-4bit --reasoning-parser deepseek_r1

# High quality general
vllm-mlx serve mlx-community/Qwen3-8B-8bit

# Multi-user high throughput
vllm-mlx serve mlx-community/Qwen3-4B-8bit --continuous-batching --max-num-seqs 256
```

### 64GB+ Mac (M2 Ultra, M3 Ultra, M4 Max 128GB)

Large models and high concurrency:

```bash
# Large models
vllm-mlx serve mlx-community/Nemotron-30B-4bit

# Very high concurrency
vllm-mlx serve mlx-community/Qwen3-8B-8bit \
  --continuous-batching \
  --max-num-seqs 512 \
  --cache-memory-percent 0.30
```

## By Task

### Chat / Assistant

| Quality  | Model                      | Command                                                   |
| -------- | -------------------------- | --------------------------------------------------------- |
| Fast     | Qwen3-0.6B-8bit            | `vllm-mlx serve mlx-community/Qwen3-0.6B-8bit`            |
| Balanced | Llama-3.2-3B-Instruct-4bit | `vllm-mlx serve mlx-community/Llama-3.2-3B-Instruct-4bit` |
| Quality  | Qwen3-8B-4bit              | `vllm-mlx serve mlx-community/Qwen3-8B-4bit`              |

### Code Generation

```bash
# Fast code completion
vllm-mlx serve mlx-community/Qwen3-4B-8bit

# Better code quality
vllm-mlx serve mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit
```

### Reasoning / Math

```bash
# DeepSeek R1 (chain-of-thought)
vllm-mlx serve mlx-community/DeepSeek-R1-0528-Qwen3-8B-4bit --reasoning-parser deepseek_r1

# Qwen3 thinking mode
vllm-mlx serve mlx-community/Qwen3-8B-8bit --reasoning-parser qwen3
```

### Vision Understanding

```bash
# Document analysis
vllm-mlx serve mlx-community/Qwen2-VL-7B-Instruct-4bit

# General vision
vllm-mlx serve mlx-community/LLaVA-1.5-7B-4bit
```

### Multi-User Production

```bash
# Optimized for throughput
vllm-mlx serve mlx-community/Qwen3-4B-8bit \
  --continuous-batching \
  --max-num-seqs 256 \
  --cache-memory-percent 0.20
```

## Model Formats

vLLM-MLX works with MLX-format models from HuggingFace:

- **4bit quantized** (`*-4bit`): Smallest, fastest, slight quality loss
- **8bit quantized** (`*-8bit`): Good balance of size and quality
- **bf16/fp16**: Full precision, largest memory, best quality

Most mlx-community models are pre-quantized and ready to use.

## Download Models

Pre-download models for faster startup:

```bash
# Download before serving
huggingface-cli download mlx-community/Qwen3-4B-8bit

# Check what's cached
ls ~/.cache/huggingface/hub/ | grep mlx
```

## Performance Notes

- First request is slow (model loading)
- Subsequent requests use cached model
- Continuous batching significantly improves multi-user throughput
- Quantized models (4bit/8bit) use less memory with minimal quality loss
- Prefix caching speeds up repeated prompts/images
