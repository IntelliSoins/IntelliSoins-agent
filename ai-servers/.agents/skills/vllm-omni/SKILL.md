---
name: vllm-omni

description: vLLM-Omni — serving de modèles omni-modalité (texte, image, vidéo, audio) sur GPU/NPU CUDA/ROCm via API OpenAI unifiée, étend vLLM aux Diffusion Transformers (DiT). NON supporté sur Apple Silicon (utiliser mflux/mlx-video/mlx-audio). Charge on-demand sur fichiers vllm-omni.
paths:
  - "**/*vllm*omni*"
  - "**/stage-config*"
---

# vLLM-Omni — Omni-Modality Model Serving (rule on-demand)

> **Provenance** : transféré du skill `intellisoins-mlx:vllm-omni` (`SKILL.md`) le 2026-05-24. Détail catalogue modèles + API → `~/.claude/rules/vllm-omni/models-and-apis.md`.
> **⚠️ GPU/NPU Linux uniquement** — pas Apple Silicon. Pour génération image/vidéo/audio sur Mac, voir `mflux` / `mlx-video` / `mlx-audio`. Distinct de `vmlx`, `vllm-mlx`, `vllm-metal` (eux sur Apple Silicon).

Framework for efficient serving of omni-modality models: text, image, video, and audio
generation via a unified OpenAI-compatible API. Extends vLLM beyond autoregressive LLMs
to support Diffusion Transformers (DiT) and non-autoregressive architectures.

**Upstream**: https://github.com/vllm-project/vllm-omni (official)
**Fork**: https://github.com/Blaizzy/vllm-omni (Prince Canuma / Blaizzy)
**Docs**: https://vllm-omni.readthedocs.io/
**License**: Apache 2.0
**Version**: v0.18.0 (stable, 2026-03-28) — rebased to upstream vLLM v0.18.0
**Latest prerelease**: v0.20.0rc1 (2026-05-01) — rebased to vLLM v0.20.0

## Platform Requirements

| Requirement   | Value                                                         |
| ------------- | ------------------------------------------------------------- |
| OS            | Linux                                                         |
| Python        | 3.12                                                          |
| GPU           | NVIDIA CUDA or AMD ROCm                                       |
| NPU           | Supported (subset of models)                                  |
| Apple Silicon | Not supported (use `vllm-mlx` or `vllm-metal` skills instead) |

## Installation

```bash
uv venv --python 3.12 --seed
source .venv/bin/activate

# CUDA
uv pip install vllm==0.18.0 --torch-backend=auto

# ROCm
uv pip install vllm==0.18.0 --extra-index-url https://wheels.vllm.ai/rocm/0.18.0/rocm700

git clone https://github.com/vllm-project/vllm-omni.git
cd vllm-omni
uv pip install -e .
```

## Supported Models Overview

### Omni-Modality (text + image + audio in/out)

| Model               | HuggingFace                               | Notes                          |
| ------------------- | ----------------------------------------- | ------------------------------ |
| Qwen3-Omni-30B-A3B  | `Qwen/Qwen3-Omni-30B-A3B-Instruct`        | MoE, latest                    |
| Qwen2.5-Omni-7B/3B  | `Qwen/Qwen2.5-Omni-7B`                    | Multi-modal I/O                |
| MammothModa2        | `bytedance-research/MammothModa2-Preview` | Omni-modal (v0.18.0+)          |
| Ming-flash-omni-2.0 | `inclusionAI/Ming-flash-omni-2.0`         | Omni-modal flash (v0.20.0rc1+) |
| Dynin-omni          | `snu-aidas/Dynin-Omni`                    | Omni-modal (v0.20.0rc1+)       |

### Image Generation (Diffusion)

| Model                | HuggingFace                               | Type                                            |
| -------------------- | ----------------------------------------- | ----------------------------------------------- |
| Z-Image Turbo        | `Tongyi-MAI/Z-Image-Turbo`                | Fast DiT                                        |
| Qwen-Image           | `Qwen/Qwen-Image`                         | T2I                                             |
| Qwen-Image-2512      | `Qwen/Qwen-Image-2512`                    | T2I high-res                                    |
| BAGEL-7B-MoT         | `ByteDance-Seed/BAGEL-7B-MoT`             | DiT-only MoT                                    |
| Ovis-Image           | `OvisAI/Ovis-Image`                       | T2I                                             |
| LongCat-Image        | `meituan-longcat/LongCat-Image`           | T2I                                             |
| Stable Diffusion 3.5 | `stabilityai/stable-diffusion-3.5-medium` | DiT                                             |
| FLUX.2-klein 4B/9B   | `black-forest-labs/FLUX.2-klein-4B`       | DiT                                             |
| FLUX.1-dev           | `black-forest-labs/FLUX.1-dev`            | DiT                                             |
| FLUX.2-dev           | `black-forest-labs/FLUX.2-dev`            | DiT (v0.18.0+)                                  |
| FLUX.1-Kontext-dev   | `black-forest-labs/FLUX.1-Kontext-dev`    | DiT context-aware (v0.18.0+)                    |
| Hunyuan Image3 AR    | `tencent/HunyuanImage-3.0`                | Tencent Hunyuan AR (v0.18.0+, closest officiel) |

### Image Editing

| Model                | HuggingFace                          |
| -------------------- | ------------------------------------ |
| Qwen-Image-Edit      | `Qwen/Qwen-Image-Edit`               |
| Qwen-Image-Edit-2509 | `Qwen/Qwen-Image-Edit-2509`          |
| Qwen-Image-Layered   | `Qwen/Qwen-Image-Layered`            |
| LongCat-Image-Edit   | `meituan-longcat/LongCat-Image-Edit` |

### Video Generation

| Model            | HuggingFace                                                     |
| ---------------- | --------------------------------------------------------------- |
| Wan2.2-T2V-A14B  | `Wan-AI/Wan2.2-T2V-A14B-Diffusers`                              |
| Wan2.2-TI2V-5B   | `Wan-AI/Wan2.2-TI2V-5B-Diffusers`                               |
| Wan2.2-I2V-A14B  | `Wan-AI/Wan2.2-I2V-A14B-Diffusers`                              |
| LTX-2            | `Lightricks/LTX-Video` (v0.18.0+, repo officiel Lightricks LTX) |
| LTX-2.3          | `Lightricks/LTX-2.3` (v0.20.0rc1+)                              |
| HunyuanVideo-1.5 | `tencent/HunyuanVideo-1.5` (v0.18.0+)                           |
| FastGen Wan 2.1  | (v0.20.0rc1+ — HF ID NON VERIFIE)                               |

### Audio

| Model                 | HuggingFace                                                    |
| --------------------- | -------------------------------------------------------------- |
| Stable-Audio-Open     | `stabilityai/stable-audio-open-1.0`                            |
| Qwen3-TTS 1.7B/0.6B   | `Qwen/Qwen3-TTS-12Hz-1.7B-Base`                                |
| Voxtral TTS           | `mistralai/Voxtral-4B-TTS-2603` (v0.18.0+)                     |
| MiMo-Audio            | `XiaomiMiMo/MiMo-Audio-7B-Base` (v0.18.0+)                     |
| Fish Speech S2 Pro    | `AEmotionStudio/fish-speech-s2-pro` (v0.18.0+, 3rd party fork) |
| MiMo-V2.5-ASR         | `XiaomiMiMo/MiMo-V2.5-ASR` (v0.20.0rc1+)                       |
| MOSS-TTS-Nano         | `OpenMOSS-Team/MOSS-TTS-Nano-100M` (v0.20.0rc1+)               |
| VoxCPM2 native AR TTS | `openbmb/VoxCPM2` (v0.20.0rc1+)                                |

For complete model catalog with NPU support: `~/.claude/rules/vllm-omni/models-and-apis.md`

## Quick Start — Offline Inference

```python
from vllm_omni.entrypoints.omni import Omni

omni = Omni(model="Tongyi-MAI/Z-Image-Turbo")
outputs = omni.generate("a cup of coffee on the table")
outputs[0].request_output[0].images[0].save("coffee.png")
```

## Quick Start — Online Serving

### Launch Server

```bash
vllm serve Tongyi-MAI/Z-Image-Turbo --omni --port 8000
```

The `--omni` flag activates the omni-modality pipeline (required for all non-LLM models).

### Image Generation API (OpenAI DALL-E compatible)

```bash
curl -X POST http://localhost:8000/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a dragon over Green Mountains",
    "size": "1024x1024",
    "num_inference_steps": 50,
    "guidance_scale": 4.0,
    "seed": 42
  }' | jq -r '.data[0].b64_json' | base64 -d > dragon.png
```

### Image Edit API

```bash
vllm serve Qwen/Qwen-Image-Edit-2511 --omni --port 8000

curl -X POST http://localhost:8000/v1/images/edits \
  -F "image=@input.png" \
  -F "prompt='make the bear wear sportswear'" \
  -F "size=1024x1024"
```

### Chat Completions API (Omni models)

```bash
vllm serve Qwen/Qwen2.5-Omni-7B --omni --port 8000

curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "describe this scene"}],
    "extra_body": {"height": 1024, "width": 1024}
  }'
```

## Architecture — OmniConnector

vLLM-Omni introduces a **heterogeneous pipeline abstraction** via OmniConnector:

- **Stage-based execution**: Models decomposed into stages with pipelined overlapping
- **Dynamic resource allocation**: GPU memory managed across stages
- **KV cache management**: Inherited from vLLM for autoregressive components
- **Distributed inference**: Tensor, pipeline, data, and expert parallelism

Configure stage behavior via `stage_configs_path` YAML:

```python
omni = Omni(model="...", stage_configs_path="./stage-config.yaml")
```

## What's New v0.18.0 (2026-03-28)

- **Rebased to upstream vLLM v0.18.0** — major entrypoint refactor (PD disaggregation
  scaffolding, coordinator support, multimodal output decoupling), scheduler/executor
  refactoring + runtime cleanups.
- **Audio/Speech/Omni production hardening**: Qwen3-TTS, Qwen3-Omni, MiMo-Audio,
  Fish Speech S2 Pro, Voxtral TTS — lower latency, better concurrency, robust streaming.
- **Diffusion optim**: cache-dit / TeaCache integration, TP/SP/HSDP support, faster startup.
- **Unified quantization framework**: INT8, FP8, GGUF coverage across diffusion + image workloads.
- **RL E2E**: Qwen-Image end-to-end RL with verl + Flow-GRPO training, collective RPC support.
- **New models**: Helios, Helios-Mid/Distilled, MammothModa2, Fun CosyVoice3-0.5B-2512,
  FLUX.2-dev, FLUX.1-Kontext-dev, Hunyuan Image3 AR, DreamID-Omni, LTX-2, HunyuanVideo-1.5.

### Coming in v0.20.0rc1 (2026-05-01, prerelease)

- **Rebased to upstream vLLM v0.20.0** + sleep-mode support + coordinator reliability fixes.
- **TTS hardening**: lower VRAM, CUDA graph reuse, voice-cloning fixes, deterministic
  Fish Speech, universal TTS benchmark.
- **Diffusion**: Z-Image image-to-image, FLUX.1/FLUX.2 TeaCache + CFG-parallel paths,
  VAE tiling, MP4 latency optimization.
- **BAGEL**: LoRA support, think mode, fused projections, layerwise offload, diffusion metrics.
- **HW broadening**: CUDA + ROCm + MUSA flash attention + NPU graph/fused-op + AMD CI +
  XPU torch inductor + OmniGen2 FP8 + HunyuanImage3 NPU quantization.
- **New models**: MagiHuman, Dynin-omni, InternVLA-A1, Ming-flash-omni-2.0, MiMo-V2.5-ASR,
  MOSS-TTS-Nano, VoxCPM2 native AR TTS, LTX-2.3, FastGen Wan 2.1.

## API Extension Parameters

Beyond standard OpenAI parameters, vLLM-Omni adds:

| Parameter             | Type   | Description                                     |
| --------------------- | ------ | ----------------------------------------------- |
| `negative_prompt`     | string | What to avoid in generation                     |
| `num_inference_steps` | int    | Diffusion steps (more = higher quality, slower) |
| `guidance_scale`      | float  | CFG scale (0.0-20.0 typical)                    |
| `true_cfg_scale`      | float  | Model-specific true CFG                         |
| `seed`                | int    | Reproducibility                                 |

## Relation to Other Skills/Rules

| Cible                | Target               | Use Case                                    |
| -------------------- | -------------------- | ------------------------------------------- |
| **vllm-omni** (this) | GPU/NPU (CUDA, ROCm) | Omni-modal: images, video, audio, diffusion |
| `vllm-mlx`           | Apple Silicon MLX    | LLM/VLM serving on Mac                      |
| `vllm-metal`         | Apple Silicon Metal  | vLLM with Metal GPU plugin                  |
| `vmlx`               | Apple Silicon MLX    | Moteur d'inférence MLX local complet        |
| `mflux`              | Apple Silicon MLX    | Image generation (FLUX, Z-Image) locally    |
| `mlx-video`          | Apple Silicon MLX    | Video generation (LTX, Wan) locally         |

**Key distinction**: vLLM-Omni requires CUDA/ROCm GPU. For Apple Silicon image/video/audio
generation, use `mflux`, `mlx-video`, or `mlx-audio` instead.

## Additional Resources

`~/.claude/rules/vllm-omni/models-and-apis.md` — Complete model catalog (GPU + NPU), API endpoint
reference for image generation, image editing, chat completions, extension parameters,
Python SDK examples, error handling, and stage configuration.
