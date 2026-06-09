---
description: TurboQuant — compression KV-cache pour inférence MLX sur Apple Silicon (3-5× via rotation PolarQuant + quantization, Google Research mars 2026). 6 chemins d'intégration (mlx-vlm, mlx-openai-server, mlx-optiq, llama.cpp, SwiftLM, helgklaizar v1). Patch MoE-aware Qwen3.5. Déployé dans ~/ai-servers/. Charge on-demand sur fichiers turboquant ou servers.yaml.
paths:
  - "~/ai-servers/**"
  - "**/servers.yaml"
  - "**/*turboquant*"
---

# TurboQuant MLX — KV-Cache Compression (rule on-demand)

> **Provenance** : transféré du skill `intellisoins-mlx:turboquant-mlx` (`SKILL.md`) le 2026-05-24. Pas de references upstream (fichier unique). Pour TurboQuant intégré au plugin Metal, voir aussi `~/.claude/rules/vllm-metal.md`. Setup local : `~/.claude/rules/local-ai-stack.md`.

Google Research (March 25, 2026) — training-free, data-oblivious vector quantization
compressing KV-cache to 1-3 bits per value. Core algorithm: **PolarQuant** (Cartesian-to-Polar
transformation for unbiased dot-product estimation). Up to 5.3x memory reduction, quality preserved.

**Note (2026-04-10)**: QJL (Quantized Johnson-Lindenstrauss error correction) a été **abandonné**
dans la v1 flagship après validation communautaire — introduit de la variance qui dégrade
la qualité softmax. PolarQuant seul donne de meilleurs résultats.

**Paper**: "TurboQuant: Online Vector Quantization with Near-optimal Distortion Rate"
(Zandieh, Daliri, Hadian, Mirrokni — Google Research). arXiv:2504.19874. Accepted ICLR 2026.

## Repos & Integration Paths

| Path  | Tool                                 | Method                                                       | Best for                                              |
| ----- | ------------------------------------ | ------------------------------------------------------------ | ----------------------------------------------------- |
| **A** | **mlx-vlm** (v0.4.4+)                | `--kv-bits 3.5 --kv-quant-scheme turboquant`                 | Multimodal (vision), quick setup                      |
| **B** | **mlx-openai-server** + monkey-patch | `turboquant_patch.py` → `TurboQuantKVCacheV2`                | Production servers, aictl                             |
| **C** | **mlx-optiq**                        | `pip install mlx-optiq` + Python API                         | Standalone library                                    |
| **D** | **llama.cpp** (fork)                 | `--cache-type-k tbq3_0 --cache-type-v tbq3_0`                | GGUF models                                           |
| **E** | **SwiftLM**                          | Native Swift, OpenAI-compatible                              | Swift apps                                            |
| **F** | **helgklaizar v1** flagship          | `apply_turboquant_cache()` drop-in `mlx_lm` + Asymmetric K/V | Python standalone, `pip install -e .`, PolarQuant pur |

### Source repos

| Repo                                                                                                         | Focus                                                                          | API                                                                         |
| ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------ | --------------------------------------------------------------------------- |
| **[helgklaizar/turboquant-mlx](https://github.com/helgklaizar/turboquant-mlx)** (hyphen, v1 flagship, actif) | PolarQuant pur, Asymmetric K/V, Boundary V, Attention Sink, OpenAI server, EXO | `apply_turboquant_cache(model, k_theta_bits, v_theta_bits, fp16_sink_size)` |
| [helgklaizar/turboquant_mlx](https://github.com/helgklaizar/turboquant_mlx) (underscore, legacy)             | 1-3 bit V1/V2/V3 caches, QJL inclus                                            | `TurboQuantKVCacheV2(...)` + `turboquant.patch.apply()`                     |
| [rachittshah/mlx-turboquant](https://github.com/rachittshah/mlx-turboquant)                                  | Clean standalone PoC, fractional bits (2, 3, 3.5, 4), bench suite              | Standalone                                                                  |
| [flovflo/turboquant-mlx-qwen35-kv](https://huggingface.co/flovflo/turboquant-mlx-qwen35-kv)                  | Qwen3.5-35B-A3B specific, MoE-aware, benchmarked                               | Modèle HF                                                                   |

Dernier push v1 flagship: 2026-04-10 — "ECO-MLX Hub integration, src-layout migration".

## When to Use

- Long-context inference where KV-cache becomes the memory bottleneck
- Models with **full attention layers** (100% KV-cache): Gemma 3, Qwen3, Llama, Mistral
- NOT beneficial for hybrid architectures (GatedDeltaNet, Mamba) where <30% of layers use KV-cache

## Architecture Compatibility

TurboQuant compresses standard scaled dot-product attention KV-caches.
MoE/hybrid models require **selective layer patching** (only KVCache layers, not ArraysCache/SSM layers).

| Architecture                               | KV-cache layers  | Benefit         | Patch mode            |
| ------------------------------------------ | ---------------- | --------------- | --------------------- |
| **Gemma 4 E2B / E4B** (dense + PLE)        | 100%             | **High**        | All layers            |
| **Gemma 4 26B-A4B** (MoE)                  | Varies (inspect) | **High**        | MoE-aware (selective) |
| **Gemma 4 31B** (dense)                    | 100%             | **High**        | All layers            |
| Gemma 3 / MedGemma (full attention)        | 40/40 (100%)     | High            | All layers            |
| Qwen3 dense (8B, 30B-A3B)                  | 100%             | High            | All layers            |
| Llama, Mistral, Phi                        | 100%             | High            | All layers            |
| **Qwen3.5-35B-A3B** (DeltaNet + Attention) | **10/40 (25%)**  | **Significant** | MoE-aware (see below) |
| Nemotron-H (Mamba2 + MoE + Attention)      | ~12%             | Marginal        | MoE-aware             |

### Qwen3.5 MoE — Mixed Attention Architecture

Qwen3.5-35B-A3B has `full_attention_interval=4`: 10 full-attention layers use `KVCache`,
30 GatedDeltaNet layers use `ArraysCache(size=2)` (conv + SSM state, NOT key-value pairs).

**Critical**: replacing ALL 40 layers with TurboQuantKVCacheV2 crashes — ArraysCache uses
`__getitem__`/`__setitem__`, incompatible with `update_and_fetch()`.

The model defines `make_cache()` returning a heterogeneous list:

```python
# mlx_lm/models/qwen3_5.py line 298
def make_cache(self):
    return [ArraysCache(size=2) if l.is_linear else KVCache() for l in self.layers]
```

**MoE-aware patch** — replace only KVCache instances:

```python
if hasattr(model, "make_cache"):
    from mlx_lm.models.cache import KVCache
    caches = model.make_cache()
    return [
        TurboQuantKVCacheV2(head_dim=head_dim, bits=bits,
            group_size=group_size, seed=42 + i)
        if isinstance(c, KVCache) else c
        for i, c in enumerate(caches)
    ]
```

Despite only 10/40 layers compressed, benchmarks show **significant gains** at longer contexts
because the full-attention layers dominate memory at scale.

### Inspect model layer types

```python
import mlx_lm
model, _ = mlx_lm.load("mlx-community/model-name")
if hasattr(model, "make_cache"):
    from mlx_lm.models.cache import KVCache, ArraysCache
    caches = model.make_cache()
    kv = sum(1 for c in caches if isinstance(c, KVCache))
    other = len(caches) - kv
    print(f"KVCache: {kv}, Other: {other} — TurboQuant applies to {kv} layers")
else:
    print(f"All {len(model.layers)} layers use KVCache — full TurboQuant benefit")
```

## Modes

| Mode       | Bits | Compression | Speed impact | Quality                  |
| ---------- | ---- | ----------- | ------------ | ------------------------ |
| V2 4-bit   | 4    | ~3x         | ~30% slower  | Identical                |
| V2 3.5-bit | 3.5  | ~4.6x       | ~30% slower  | Very close (recommended) |
| V2 3-bit   | 3    | ~4x         | ~30% slower  | Very close               |

V3 (Lloyd-Max, 3.5-bit) exists but is 5-6x slower — not recommended for server use.

**Fractional bits (3.5)**: asymmetric quantization — 3-bit for Keys + 4-bit for Values.
Superior to uniform allocation at the same total bit budget. Best quality/compression ratio.

## Benchmarks

### Gemma 4 31B (dense, 128K context)

| Metric      | Without TurboQuant (FP16 KV) | TurboQuant 3.5-bit | Delta       |
| ----------- | ---------------------------- | ------------------ | ----------- |
| KV Memory   | 13.3 GB                      | 4.9 GB             | **-63%**    |
| Peak Memory | 75.2 GB                      | 65.8 GB            | **-9.4 GB** |
| Quality     | Baseline                     | Preserved          | ~0 loss     |

Context window impact (24 GB Mac, model 4-bit ~18 GB):

- Without TurboQuant: ~16K tokens max before OOM
- With TurboQuant 3.5-bit: ~100K+ tokens viable

### MedGemma 27B (dense, 200 tokens gen)

| Config        | tok/s | Cache size | Compression |
| ------------- | ----- | ---------- | ----------- |
| Standard fp16 | 20.9  | 144 MB     | 1x          |
| TQ V2 4-bit   | 14.2  | 39 MB      | 3.1x        |
| TQ V2 3-bit   | 14.3  | 32 MB      | 3.8x        |

KV-cache per token (MedGemma 27B fp16): ~496 KB. At 16K context: 8.3 GB → ~2.1 GB at 3-bit.

### Qwen3.5-35B-A3B (MoE, 2048 prompt / 8 gen tokens, 3 trials)

| Backend              | Prompt tok/s | Gen tok/s | Gen wall (s) | Cache        |
| -------------------- | ------------ | --------- | ------------ | ------------ |
| Baseline             | 514.34       | 35.67     | 5.67         | 80.12 MB     |
| mlx_quant            | 516.13       | 38.30     | 5.16         | 44.77 MB     |
| **TurboQuant 3-bit** | **679.14**   | **44.83** | **4.20**     | **45.10 MB** |

**vs Baseline**: +32% prompt, +26% decode, -26% wall time, -44% cache memory.

At shorter contexts (128 tokens), gains are primarily memory (-12% cache) with minimal speed difference.
TurboQuant shines at **1K+ context tokens** where KV-cache becomes the bottleneck.

## Path F: helgklaizar v1 Flagship — Drop-in mlx-lm (simplest Python)

Repo **[helgklaizar/turboquant-mlx](https://github.com/helgklaizar/turboquant-mlx)** (2026-04-10).
Plug direct dans `mlx_lm` via 2 lignes, sans modifier la logique interne. PolarQuant pur (pas de QJL).

### Features exclusives v1

- **Asymmetric K/V**: keys précis (`k_theta_bits=8`), values agressivement compressés (`v_theta_bits=3`)
- **Boundary V**: premières 2 et dernières 2 couches laissées non-compressées (récupère ~90% précision perdue)
- **Attention Sink**: premiers N tokens (ex: 128) en fp16 pour préserver instruction-following
- **Dynamic Chunking Buffer**: cache par segments de 64 tokens (VRAM minimal en longue génération)
- **EXO Cluster Ready**: compatible inférence décentralisée Apple Silicon

### Installation

```bash
git clone https://github.com/helgklaizar/turboquant-mlx.git
cd turboquant-mlx
pip install -e .
```

### Usage Python

```python
from mlx_lm import load
from turboquant_mlx.plugins.cache_plugin import apply_turboquant_cache

model, tokenizer = load("mlx-community/Meta-Llama-3-8B-Instruct-4bit")

# Asymmetric: keys 8-bit, values 3-bit, 128 premiers tokens non-compressés
apply_turboquant_cache(model, k_theta_bits=8, v_theta_bits=3, fp16_sink_size=128)

# Toute génération consomme ~70% moins de mémoire KV-cache
```

### Serveur OpenAI-compatible

```bash
python scripts/run_server.py --model mlx-community/Meta-Llama-3-8B-Instruct-4bit --port 8080
```

Compatible avec Jan, Chatbox, Open WebUI (pointer vers `http://localhost:8080/v1`).
**Non compatible LM Studio** (runtime bundled, pas d'accès à la couche `mlx_lm` cache).

### Compatibilité validée (Needle-in-a-Haystack 100%)

| Modèle                       | 3-bit | Notes                                               |
| ---------------------------- | ----- | --------------------------------------------------- |
| DeepSeek-R1-Distill-8B-4bit  | ✅    | Reasoning complexe préservé                         |
| Mistral-Nemo-12B-4bit        | ✅    | Layout robuste pour PolarQuant                      |
| Llama-3-8B / 3.2-1B          | ✅    | Dot-product flawless                                |
| Qwen2.5-7B / Qwen3.5-35B-A3B | ✅    | Via lazy KV init (testé M4 Max 64GB)                |
| gemma-2-2b-it-4bit           | ❌    | Embeddings natifs clashent avec transfo polar 3-bit |

### Mémoire Llama 3 8B (FP16 vs TurboQuant 3-bit)

| Contexte | FP16    | TurboQuant 3-bit | Économie | Compression |
| -------- | ------- | ---------------- | -------- | ----------- |
| 4K       | 64 MB   | 12 MB            | 81%      | 5.3x        |
| 16K      | 256 MB  | 48 MB            | 81%      | 5.3x        |
| 64K      | 1024 MB | 192 MB           | 81%      | 5.3x        |
| 128K     | 2048 MB | 384 MB           | 81%      | 5.3x        |

## Path A: mlx-vlm Native Integration (simplest)

mlx-vlm v0.4.4+ includes TurboQuant with custom Metal kernels (fused quantize/dequantize).

```bash
pip install mlx-vlm>=0.4.4
```

### Generate (text + vision)

```bash
mlx_vlm.generate \
  --model mlx-community/gemma-4-e4b-it-8bit \
  --image ordonnance.jpg \
  --prompt "Extrais les médicaments" \
  --kv-bits 3.5 \
  --kv-quant-scheme turboquant
```

### Server (OpenAI-compatible)

```bash
mlx_vlm.server \
  --model mlx-community/gemma-4-e4b-it-8bit \
  --port 8080 \
  --kv-bits 3.5 \
  --kv-quant-scheme turboquant
```

Endpoint: `http://localhost:8080/v1/chat/completions`

### Gemma 4 models for mlx-vlm

```
mlx-community/gemma-4-e2b-it-8bit
mlx-community/gemma-4-e4b-it-8bit
unsloth/gemma-4-E4B-it-UD-MLX-4bit
unsloth/gemma-4-26B-A4B-it-UD-MLX-4bit
unsloth/gemma-4-31B-it-UD-MLX-4bit
```

## Path B: mlx-openai-server Monkey-Patch (production)

### Installation

Source package (no pip). Copy into the target venv:

```bash
git clone --depth 1 https://github.com/sharpner/turboquant-mlx.git /tmp/turboquant-mlx
cp -r /tmp/turboquant-mlx/turboquant <venv>/lib/python3.12/site-packages/turboquant
```

Dependencies: `mlx` + `mlx-lm` (already in MLX inference venvs).

## Path B (cont.): Server Integration (mlx-openai-server)

Two files in `~/ai-servers/`:

### turboquant_patch.py

Monkey-patches `make_prompt_cache` → `TurboQuantKVCacheV2` and applies SDPA dispatch.

```python
import turboquant_patch
turboquant_patch.apply(bits=3)
```

Env vars: `TURBOQUANT_BITS` (default 3), `TURBOQUANT_GROUP_SIZE` (default 64), `TURBOQUANT_DISABLED=1` to bypass.

### launchers/turboquant_server.py

Wrapper that resolves `app` module namespace collision, patches, then launches the server CLI.

### Launcher example

```bash
export TURBOQUANT_BITS=3
exec python ~/ai-servers/launchers/turboquant_server.py launch \
    --model-path mlx-community/model-name \
    --port 8080 --host 127.0.0.1 ...
```

LRU Prompt Cache compatibility confirmed: `update_and_fetch`, `deepcopy`, `trim`, `is_trimmable`, `nbytes` all work.

## Standalone Benchmark

### Dense models (MedGemma, Llama, Qwen3 dense)

```python
import mlx_lm
from turboquant.cache_v2 import TurboQuantKVCacheV2
import turboquant.patch as tq_patch

tq_patch.apply()
model, tokenizer = mlx_lm.load("mlx-community/model-name")
head_dim = model.args.head_dim

tq_cache = [
    TurboQuantKVCacheV2(head_dim=head_dim, bits=3, group_size=64, seed=42 + i)
    for i in range(len(model.layers))
]
```

### MoE/hybrid models (Qwen3.5-35B-A3B)

```python
import mlx_lm
from mlx_lm.models.cache import KVCache
from turboquant.cache_v2 import TurboQuantKVCacheV2
import turboquant.patch as tq_patch

tq_patch.apply()
model, tokenizer = mlx_lm.load("mlx-community/Qwen3.5-35B-A3B-4bit")
head_dim = model.args.head_dim
bits, group_size = 3, 64

# Selective: only replace KVCache layers, keep ArraysCache for GatedDeltaNet
caches = model.make_cache()
tq_cache = [
    TurboQuantKVCacheV2(head_dim=head_dim, bits=bits, group_size=group_size, seed=42 + i)
    if isinstance(c, KVCache) else c
    for i, c in enumerate(caches)
]
# 10 TurboQuantKVCacheV2 + 30 ArraysCache(size=2)
```

## Local Setup (Michael's ai-servers)

Files: `~/ai-servers/turboquant_patch.py` (monkey-patch), `~/ai-servers/launchers/turboquant_server.py` (wrapper).
Package installed in: `~/.venvs/mlx-qwen35/lib/python3.12/site-packages/turboquant/` (V1, V2, V3 caches).
Server management: `aictl start|stop|restart|logs <server-name>`.

| Server          | Port | TurboQuant        | Config                                            |
| --------------- | ---- | ----------------- | ------------------------------------------------- |
| MedGemma 27B    | 8080 | Active (V2 3-bit) | `servers.yaml` → `launchers/turboquant_server.py` |
| Qwen3.5-35B-A3B | 8087 | Pending MoE patch | `servers.yaml` → `launchers/qwen35-35b.sh`        |

To enable on Qwen3.5: modify `turboquant_patch.py` for MoE-aware detection (see Architecture Compatibility),
then switch `qwen35-35b.sh` to use `turboquant_server.py`.

## Troubleshooting

| Issue                                | Cause                                        | Fix                                                 |
| ------------------------------------ | -------------------------------------------- | --------------------------------------------------- |
| `AttributeError: __setitem__` on MoE | All layers replaced with TurboQuantKVCacheV2 | Use MoE-aware patch (selective KVCache replacement) |
| `AttributeError: self_attn`          | Hybrid model without standard attention      | Check compatibility table                           |
| `app` module not found               | Namespace collision                          | Use `turboquant_server.py` wrapper                  |
| No memory gain                       | <30% full attention layers                   | Model may not benefit enough                        |
| Quality degradation                  | 3-bit too aggressive                         | Try `TURBOQUANT_BITS=4`                             |
| Keepalive restart loop               | Server crash on model load                   | `aictl stop <name>` immediately, check logs         |
