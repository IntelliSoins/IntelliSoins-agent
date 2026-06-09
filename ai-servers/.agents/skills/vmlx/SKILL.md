---
name: vmlx

description: Moteur d'inférence MLX local sur Apple Silicon (vMLX, Jinho Jang) — LLM/vision/image-gen/audio/multimodal Nemotron-Omni, 5-layer KV caching, JANG quantization, inférence distribuée multi-Mac, API Anthropic+OpenAI+Ollama native. Charge on-demand quand on travaille dans la stack ai-servers ou sur des fichiers vmlx.
paths:
  - "~/ai-servers/**"
  - "**/servers.yaml"
  - "**/*vmlx*"
---

# vMLX — Moteur d'inférence MLX local (rule on-demand)

> **Provenance** : transféré du skill `intellisoins-mlx:vmlx` (`SKILL.md`) le 2026-05-24, pour sortir le contenu de l'always-loaded des 6 projets qui activent `intellisoins-mlx` (`ai-servers`, `master-IA`, `openclaw`, `Finances_Assurances`, `postgresml-build`, `organisateur-complet`). Détail caching / JANG / API → sous-rules `~/.claude/rules/vmlx/`.
> Membre de la stack locale — voir aussi `~/.claude/rules/local-ai-stack.md`.

Free, open-source MLX inference engine for Apple Silicon by Jinho Jang — [vmlx.net](https://vmlx.net).
Uniquely combines text, vision, image generation, audio, 5-layer KV caching, and agentic tools with native Anthropic + OpenAI + Ollama API compatibility.

**Architecture du projet (mai 2026)** :

- **Engine Python + panel Electron legacy** : repo principal [jjang-ai/vmlx](https://github.com/jjang-ai/vmlx) (Apache-2.0). Tags `v1.x.x`. PyPI `vmlx` distribue cette ligne. Version actuelle : **v1.5.49** (2026-05-24).
- **vMLX v2 desktop app (Swift native, recommandé pour interaction)** : même repo [jjang-ai/vmlx](https://github.com/jjang-ai/vmlx/releases?q=tag%3Av2&expanded=true), tags `v2.0.0-rc.x` (rc) puis `v2.0.0-beta.x` (legacy). Pure SwiftUI, zero PyTorch hot-path, 50–95 t/s sur M-series (vs 11–60 t/s Python). Latest : **v2.0.0-rc.1** (2026-05-04, Developer-ID notarized + stapled, hardened runtime, Apple Team ID 55KGF2S5AY, 24.3 MB DMG).
- **`jjang-ai/mlxstudio`** : repo release-only (Electron installer distribution), en voie d'obsolescence depuis v1.4.0 qui annonce officiellement la migration Swift. À ne plus pointer pour les nouveaux usages.

**Distinct from**: vllm-mlx (waybarrios) — different project, different codebase.

## Why use vMLX over alternatives

The performance advantage comes from _context reuse_: agent workflows repeat similar prompts (system prompts, tool schemas, codebase context), so vMLX's prefix cache turns 8K-token prefills from ~49s into 1-2s. Ollama and LM Studio recompute every prefill from scratch. That difference compounds over hundreds of agent turns.

## Installation

```bash
# Base install
pip install vmlx

# With optional feature groups
pip install "vmlx[image]"  # Flux, Qwen-Image
pip install "vmlx[jang]"   # JANG adaptive quantization runtime
pip install "vmlx[audio]"  # Kokoro TTS, Whisper STT
pip install "vmlx[image,jang,audio]"  # Everything

# Alternatives
uv tool install vmlx
pipx install vmlx
```

Or download MLX Studio native macOS app at vmlx.net/download (auto-installs engine via uv, no terminal needed).

**Requirements**: Python 3.10+, macOS 14+ (macOS 26 Tahoe for latest local inference), Apple Silicon M1+.

> Note: sur macOS 14+, `pip install vmlx` direct échoue (`externally-managed-environment`). Utiliser `uv tool install vmlx`, `pipx install vmlx`, ou un venv.

## Quick Start

```bash
# Serve a model (command requires a target)
vmlx serve mlx-community/Qwen3-8B-4bit

# With KV cache quantization (saves ~4× memory)
vmlx serve mlx-community/Llama-3.2-3B-Instruct-4bit --kv-quant q8

# With speculative decoding (pair model + draft)
vmlx serve mlx-community/Qwen3-8B-4bit --speculative mlx-community/Qwen3-0.6B-4bit

# Multimodal Nemotron-Omni (image + audio + video, v1.4.0+)
vmlx serve JANGQ-AI/Nemotron-3-Nano-Omni-30B-A3B-JANGTQ4 --omni-backend stage2
```

Server binds `http://0.0.0.0:8000` by default.

## CLI Commands

```bash
vmlx serve <model>              # Start inference server
vmlx convert <model> --bits 4   # MLX uniform quantization
vmlx convert <model> -j JANG_3M # JANG adaptive quantization
vmlx info <model>               # Model metadata + config
vmlx doctor <model>             # Run diagnostics
vmlx bench <model>              # Performance benchmarks
vmlx-worker --secret <secret>   # Start distributed worker node
```

## API Compatibility

Three wire formats on a single port:

| Endpoint                          | Protocol                                    |
| --------------------------------- | ------------------------------------------- |
| `/v1/chat/completions`            | OpenAI Chat                                 |
| `/v1/messages`                    | **Anthropic Messages API**                  |
| `/api/chat`, `/api/generate`      | Ollama                                      |
| `/v1/responses`                   | OpenAI Responses API                        |
| `/v1/completions`                 | Text generation                             |
| `/v1/embeddings`                  | Vector embeddings                           |
| `/v1/rerank`                      | Document reranking (cross-encoder)          |
| `/v1/images/generations`          | Flux Schnell/Dev, Z-Image Turbo             |
| `/v1/images/edits`                | Qwen Image Edit (instruction-based, ~54 GB) |
| `/v1/audio/speech`                | Kokoro TTS                                  |
| `/v1/audio/transcriptions`        | Whisper STT                                 |
| `/v1/cluster/status\|nodes\|scan` | Multi-Mac cluster management                |
| `/v1/cache/stats`                 | Cache statistics                            |
| `/health`                         | Server health check                         |

### Connect via OpenAI or Anthropic SDK

```python
# OpenAI
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8000/v1", api_key="local")

# Anthropic — same code as cloud, pointed at localhost
import anthropic
client = anthropic.Anthropic(base_url="http://localhost:8000", api_key="local")
```

Works natively with Cursor, Continue, Aider, and Claude Code.

For full endpoint reference including image generation, audio, and Ollama format, see `~/.claude/rules/vmlx/api-reference.md`.

## Supported Architectures

53+ text architectures auto-detected: **Llama 3/3.1/3.2/3.3/4, Qwen 2/2.5/3/3.5, Mistral/Mixtral, Gemma 3/4, Phi-4, DeepSeek V2/V3/V4/R1, GLM-4, MiniMax M2.5, Nemotron/Nemotron-H, StepFun, Jamba, GatedDeltaNet, Laguna 33B/3B, Mistral-Medium-3.5-128B**. (DeepSeek V4 ajouté v1.3.96/97 — auto-route + force-thinking + default-system-prompt injection.)

- **Nemotron-3-Nano-Omni** (v1.4.0+) — multimodal text+image+audio+video, bundles MXFP4/JANGTQ4/JANGTQ2 (voir section dédiée plus bas)
- **Laguna 33B/3B** (v1.4.2+) — poolside agentic-coding MoE, hybrid SWA+full attention, 256 routed experts top-8 + 1 shared, dual-RoPE
- **Mistral-Medium-3.5-128B** (v1.4.2+) — dense GQA 96/8, 256K YaRN context, PIXTRAL vision tower
- **13 tool call parsers** (auto-configured): `qwen`, `llama`, `mistral`, `hermes`, `deepseek`, `glm47`, `minimax`, `nemotron`, `granite`, `functionary`, `xlam`, `kimi`, `step3p5`
- **3 reasoning parsers** (extrait les `<think>` blocks): `qwen3` (Qwen3, QwQ, MiniMax, StepFun), `deepseek_r1` (DeepSeek R1, Gemma 3, GLM, Phi-4), `openai_gptoss` (GLM Flash, GPT-OSS)
- Hybrid SSM/Mamba via BatchMambaCache (Nemotron-H, Jamba, GatedDeltaNet)
- Vision: Qwen-VL, Qwen3.5-VL, Pixtral, InternVL, LLaVA, Gemma 3n, Mistral-Medium-3.5 (PIXTRAL)
- Image gen: **Flux Schnell/Dev, Z-Image Turbo** (via mflux)
- Image edit: **Qwen Image Edit** (instruction-based, ~54 GB) — `vmlx serve qwen-image-edit`
- Audio: Kokoro TTS, Whisper STT (via mlx-audio)
- Embeddings + reranking (cross-encoders)

## Nemotron-3-Nano-Omni Multimodal (v1.4.0+)

Chat avec **images + audio + video** sur les bundles `JANGQ-AI/Nemotron-3-Nano-Omni-30B-A3B-{MXFP4,JANGTQ4,JANGTQ2}` via les **4 wire formats** standard :

- `/v1/chat/completions` (OpenAI)
- `/v1/messages` (Anthropic)
- `/api/chat` (Ollama)
- `/v1/responses` (OpenAI Responses, content types canoniques `input_image` / `input_audio` / `input_video` auto-normalisés vers chat-completions envelopes en v1.4.2+)

### Two encoder backends

| Backend                           | Activation                                                                           | Caractéristiques                                           |
| --------------------------------- | ------------------------------------------------------------------------------------ | ---------------------------------------------------------- |
| **Stage-1 PyTorch+MPS** (default) | rien à faire                                                                         | Bit-exact reference, plus lent — conserver pour validation |
| **Stage-2 native MLX**            | `VMLX_OMNI_BACKEND=stage2` env var **ou** `--omni-backend stage2` flag CLI (v1.4.7+) | ~17× faster RADIO + ~15× faster Parakeet                   |

**Note** : Stage-2 a des "documented quality gaps still under upstream validation" — Stage-1 reste la référence bit-exact pour les usages où la fidélité prime.

### Quick test

```bash
vmlx serve JANGQ-AI/Nemotron-3-Nano-Omni-30B-A3B-JANGTQ4 --omni-backend stage2
```

### Modalités via content blocks (`/v1/chat/completions`)

```python
client.chat.completions.create(
    model="default",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "What's in this image and what does the audio say?"},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}},
            {"type": "input_audio", "input_audio": {"data": "<base64>", "format": "wav"}},
            {"type": "video_url", "video_url": {"url": "file:///chemin/clip.mp4"}}
        ]
    }]
)
```

Voir `~/.claude/rules/vmlx/api-reference.md` pour le format complet (incl. Responses API canonique).

## 5-Layer KV Caching

The key advantage over Ollama and LM Studio for agent workloads:

| Layer                          | What it does                                                                              |
| ------------------------------ | ----------------------------------------------------------------------------------------- |
| **Prefix caching (L1)**        | Memory-aware cache qui réutilise les KV states d'anciens prompts — biggest win for agents |
| **Paged multi-context**        | 256 concurrent sequences avec dedup content-addressable                                   |
| **KV quantization**            | q4 (~4× memory savings) ou q8 (~2×); précision totale pendant la génération               |
| **Continuous batching**        | 256 inference sequences simultanément                                                     |
| **Persistent disk cache (L2)** | États KV persistent sur SSD — survive aux restart serveur                                 |
| **Block disk cache**           | Variante L2 per-block appariée au paged KV cache                                          |

Vision-language models work with the full 5-layer stack (unique to vMLX).

For detailed caching configuration, see `~/.claude/rules/vmlx/caching.md`.

## JANG Adaptive Mixed-Precision Quantization

JANG assigne des bit widths variables par layer selon la sensibilité — préserve les layers critiques (attention) à haute précision, compresse agressivement les tolérants (MLP). Amélioration dramatique vs MLX 4-bit uniforme sur gros modèles MoE.

**Benchmark vedette — MiniMax M2.5 (200 questions MMLU):**

| Quantization        | MMLU    | Size      |
| ------------------- | ------- | --------- |
| **JANG_2L (2-bit)** | **74%** | **89 GB** |
| MLX 4-bit           | 26.5%   | 120 GB    |
| MLX 3-bit           | 24.5%   | 93 GB     |
| MLX 2-bit           | 25%     | 68 GB     |

**5 profiles disponibles**: `JANG_2M` (~2.5 bits), `JANG_2L` (~2.7 bits qualité 2-bit), `JANG_3M` (~3.2 bits, **recommandé**), `JANG_4M` (~4.2 bits), `JANG_6M` (~6.2 bits, near-lossless).

Install with `pip install "vmlx[jang]"`. Format originates from the companion project [jjang-ai/jangq](https://github.com/jjang-ai/jangq) (GGUF-like for MLX). Modèles pré-quantifiés: [JANGQ-AI on HuggingFace](https://huggingface.co/JANGQ-AI).

For JANG profile selection, model conversion, and tradeoffs, see `~/.claude/rules/vmlx/jang.md`.

## Distributed Inference (Multi-Mac)

Pipeline parallelism across multiple Macs pour les modèles qui ne rentrent pas sur une seule machine. Utile pour Qwen3-72B, Llama-3.3-70B, ou Qwen3.5-Coder-Rerank-397B-A27B sur plusieurs M3 Ultra.

```bash
# Sur les Macs workers:
pip install vmlx
vmlx-worker --secret mysecret

# Sur le Mac coordinator (le serveur tourne ici):
vmlx serve JANGQ-AI/Qwen3.5-Coder-Rerank-397B-A27B-JANG_2L \
  --distributed --cluster-secret mysecret
```

**Features clés:**

- **Pipeline parallelism**: split des layers entre nodes, hidden state (~8KB/step) circule séquentiellement
- **Auto-discovery**: Bonjour mDNS, UDP broadcast, HTTP probes, Tailscale, cached peers, IP manuel
- **Capability-scored election**: le Mac le plus puissant devient coordinator automatiquement
- **Any network works**: Thunderbolt 5 (120 Gbps), 10GbE, 1GbE, WiFi, Tailscale — PP n'est pas bandwidth-bound
- **Cluster API**: endpoints REST `/v1/cluster/status`, `/v1/cluster/nodes`, `/v1/cluster/scan`
- **JANG support**: chaque worker load sa layer range depuis JANG safetensors (mmap)

Why this matters: unified memory plafonne à 512 GB sur M3 Ultra; distributed inference étend le plafond sans tomber en disk swap.

## API Gateway (MLX Studio desktop)

L'app desktop MLX Studio expose un **API Gateway** sur un port unique (défaut `8080`) qui route les requêtes vers tous les modèles chargés par leur nom. Permet de faire tourner plusieurs modèles simultanément et les accéder via une seule URL.

```bash
# Tous les modèles accessibles via le gateway
curl http://localhost:8080/v1/chat/completions \
  -d '{"model": "Qwen3.5-122B", "messages": [{"role": "user", "content": "Hi"}]}'

# Fonctionne aussi avec le CLI Ollama
OLLAMA_HOST=http://localhost:8080 ollama run Qwen3.5-122B
```

Le gateway supporte les wire formats **OpenAI**, **Anthropic**, et **Ollama**.

## Smelt Mode (Partial MoE Loading)

Charge seulement un sous-ensemble d'experts MoE en RAM ; le backbone reste résident, le routing est biaisé vers les experts chargés. Permet de faire tourner des MoE qui ne rentreraient pas autrement.

```bash
# 50% des experts par layer (défaut)
vmlx serve ./MyMoE-JANG_4M --smelt --smelt-experts 50

# Agressif : 25% — plus petit RAM, plus lent
vmlx serve ./MyMoE-JANG_4M --smelt --smelt-experts 25
```

**Benchmark `Nemotron-Cascade-2-30B-A3B-JANG_4M`** (M3 Ultra 128 GB, 23 layers MoE × 128 experts) :

| `--smelt-experts` | RAM active | Decode tok/s | RAM saving |
| ----------------- | ---------: | -----------: | ---------- |
| _off (baseline)_  |  17 408 MB |     **89.9** | —          |
| `50`              |   9 529 MB |         66.5 | **−45 %**  |
| `25`              |   5 590 MB |           \* | **−68 %**  |

\* Réponses trop courtes pour mesure fiable à 25 %. Output cohérent dans les trois cas (pas de dégradation qualité).

**Contraintes critiques** :

- **MoE seulement** (pas de modèles denses) et **format JANG seulement** (pas MLX uniforme)
- **Mutuellement exclusif avec VLM** : vMLX auto-disable `--is-mllm` avec warning. La vision tower n'est pas câblée au partial-expert loader → image input produirait des logits garbage. Pour VLM : utiliser un text-only ou désactiver smelt.
- Inspiration : [Anemll flash-moe](https://github.com/Anemll/flash-moe) (streaming experts SSD via `pread()`) ; vMLX prend une voie différente (Python/MLX, JANG, sous-ensemble fixe au démarrage).

## Speculative + Prompt Lookup Decoding

Two acceleration modes (can combine with caching):

- **Speculative decoding**: small draft model generates tokens, main model validates in batch. Pair `Qwen3-8B` with `Qwen3-0.6B` draft. Flag `--speculative-model <model>`. Typical gain 1.5–2×.
- **Prompt Lookup Decoding (PLD)**: trouve les n-grams répétés dans le prompt comme candidats de spéculation. Pas de draft model requis. Flag `--enable-pld`. Gain 20–90% sur code editing, JSON, schemas où l'output cite l'input.

## Performance (M3 Ultra, 256 GB, Llama 3.2 3B 4-bit)

| Scenario                | vMLX              | LM Studio |
| ----------------------- | ----------------- | --------- |
| 100K tokens cold TTFT   | **0.65s**         | 131.06s   |
| 100K tokens throughput  | **154,121 tok/s** | 686 tok/s |
| 2.5K tokens cached TTFT | **0.05s**         | N/A       |
| Cache speedup at 2.5K   | **9.7×**          | N/A       |

Practical impact for agents: prefill 8K context drops from ~49s → 1–2s with warm cache.

### Throughput defaults (v1.3.99+, inchangés en v1.5.49) — Macs 64 GB+

Defaults pour nouvelles sessions, optimisés pour saturer le pipeline prefill+decode :

| Setting               |                  Avant |  v1.3.99 |
| --------------------- | ---------------------: | -------: |
| Prefill Batch Size    |                    512 | **1024** |
| Prefill Step Size     |                   1024 | **2048** |
| Completion Batch Size |                    512 | **1024** |
| Cache Memory %        | 10 (panel) / 30 (auto) |   **20** |
| Max Cache Blocks      |                    500 | **1000** |
| Continuous Batching   |                     ON |       ON |
| Enable Prefix Cache   |                     ON |       ON |
| Use Paged KV Cache    |                     ON |       ON |
| Block Disk Cache (L2) |                     ON |       ON |

Sessions existantes non affectées — appliquer via "Reset all parameters to defaults" en Server Settings. Macs <64 GB tombent dans `LOW_MEM_CONFIG` (8 / 32 / 15%).

## Built-in Agentic Tools (20+)

vMLX ships 20+ tools callable by the model without external MCP setup:

- File I/O (read, write, list)
- Shell execution
- Git operations
- Web search
- Clipboard

The point is zero configuration for basic agent workflows — skip MCP entirely for local tools.

## Hardware Guide

| RAM       | Recommended models                                          |
| --------- | ----------------------------------------------------------- |
| 8 GB      | Qwen3-0.6B, Llama-3.2-1B (4-bit)                            |
| 16 GB     | Qwen3-4B, Llama-3.2-3B (4-bit/8-bit)                        |
| 32–64 GB  | Qwen3-8B, DeepSeek-R1-8B, Nemotron-30B, Qwen3.5-MoE (Smelt) |
| 128 GB+   | Qwen3.5-35B-A3B, Qwen3-72B, Llama-3.3-70B, JANG_2L profiles |
| Multi-Mac | 70B+ dense via distributed inference                        |

## vs Other MLX Inference Options

| Feature              | vMLX               | vllm-mlx (waybarrios) | Ollama 0.19 MLX  | mlx-lm direct |
| -------------------- | ------------------ | --------------------- | ---------------- | ------------- |
| Architectures        | 53+                | 30+                   | 4 (MLX runner)   | 50+           |
| Prefix cache         | ✅ 5-layer         | ✅ paged              | ❌               | ❌            |
| Anthropic API        | ✅ native          | ❌                    | ❌               | ❌            |
| Ollama API           | ✅                 | ❌                    | ✅ native        | ❌            |
| Speculative + lookup | ✅ both            | ❌                    | ❌               | ❌            |
| JANG quantization    | ✅                 | ❌                    | ❌               | ❌            |
| Mamba/SSM            | ✅                 | ❌                    | ❌               | ✅            |
| Image generation     | ✅ Flux/Z-Image    | ❌                    | ❌               | ❌            |
| Image editing        | ✅ Qwen Image Edit | ❌                    | ❌               | ❌            |
| Audio (TTS/STT)      | ✅ Kokoro/Whisper  | ❌                    | ❌               | ❌            |
| Distributed          | ✅                 | ❌                    | ❌               | ❌            |
| Built-in tools       | ✅ 20+             | ❌                    | ❌               | ❌            |
| VLM + full cache     | ✅                 | ✅                    | ❌               | ❌            |
| Peak throughput      | ~230 tok/s         | 400–525 tok/s         | 134 tok/s (int4) | ~106 tok/s    |
| Ease of use          | ⭐⭐               | ⭐⭐⭐                | ⭐⭐⭐⭐⭐       | ⭐⭐          |

## What's New v1.5.49 (2026-05-24)

- **DSV4 Flash — cache prefix composite natif** : chemin de cache prefix composite (SWA + CSA/HCA) activé par défaut, avec block indexing 256-token pour l'indexation des blocs KV.
- **Routing VL natif-MTP Qwen3.6** : aligné dans l'engine registry ; parity local-path pour DSV4 / Qwen / Hy3 / Nemotron (chargement depuis chemin local cohérent entre familles).
- **Séparation stricte des tokens** : Max Output / Context / Thinking désormais séparés strictement sur UI / CLI / Anthropic / Ollama / Responses (plus de budget partagé ambigu).

<citation>https://api.github.com/repos/jjang-ai/vmlx/releases — consulté 2026-05-29, release 2026-05-24</citation>

### Rollup v1.4.x

- **Nemotron-Omni multimodal across all 4 API surfaces** (v1.4.2) — `/v1/chat/completions`, `/v1/messages`, `/api/chat`, `/v1/responses`
- **`--omni-backend` first-class CLI flag** (v1.4.7) — équivalent runtime de `VMLX_OMNI_BACKEND=stage2`
- **Loaders Laguna 33B/3B + Mistral-Medium-3.5-128B** (v1.4.2) — `loaders/load_laguna.py` (MoE 256 routed top-8 + 1 shared, dual-RoPE, hybrid SWA+full attention) et `loaders/load_mistral3.py` (dense GQA 96/8 + 256K YaRN + PIXTRAL)
- **SSM companion RAM leak guard** (v1.4.5)
- **Laguna + Mistral3 JANGTQ guard** (v1.4.6)
- **Hard deps ajoutées** : `jang-tools` (v1.4.3), `torch` (v1.4.4 — encoder Nemotron-Omni Stage-1), `soundfile` (v1.4.8/v1.4.9 — audio Stage-2)
- **Swift v2 migration banner** dans le panel Electron (annonce officielle de la migration vers v2.0.0-rc.1 Swift native, notarized stapled)

## MLX Studio Desktop App (Electron, legacy)

> **Note** : vMLX v2 (Swift native, recommandé) est dans le repo `jjang-ai/vmlx` tag `v2.0.0-rc.x` (release candidate) — précédé des `v2.0.0-beta.x`. L'app Electron ci-dessous est la voie legacy, en voie d'obsolescence depuis la bannière v1.4.0 "vMLX is moving to Swift".

App native macOS Electron : [jjang-ai/vmlx releases v1.x.x](https://github.com/jjang-ai/vmlx/releases) (panel Electron + engine Python ensemble) ou télécharger l'installeur Electron via [vmlx.net/download](https://vmlx.net/download). Cinq modes:

| Mode       | Description                                                           |
| ---------- | --------------------------------------------------------------------- |
| **Chat**   | Conversation, historique, thinking mode, tool calling, agentic coding |
| **Server** | Gérer les sessions de modèles (start, stop, configure, monitor)       |
| **Image**  | Génération et édition avec Flux, Kontext, Qwen, Fill models           |
| **Tools**  | Converter modèles, GGUF→MLX, inspector, diagnostics                   |
| **API**    | Référence endpoints live avec code snippets copiables                 |

**Menu bar** affiche tous les modèles running, usage GPU memory, contrôles rapides. Auto-install du moteur vMLX via `uv` au premier lancement.

**Pour Swift v2 desktop app (recommandé) :** `gh release download --repo jjang-ai/vmlx --pattern '*.dmg' v2.0.0-rc.1` ou voir [releases v2 tag](https://github.com/jjang-ai/vmlx/releases?q=tag%3Av2&expanded=true).

## Sous-rules (détail on-demand)

| Sous-rule                               | Contenu                                                                                                      | Paths trigger                                                                                 |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------- |
| `~/.claude/rules/vmlx/api-reference.md` | Endpoints complets, options CLI `serve`/`convert`, VLM, agentic tools, intégration OpenClaw, troubleshooting | `**/*vmlx*client*`, `**/*vmlx*api*`, `**/*vmlx*server*`, `**/openclaw.json`, `~/.openclaw/**` |
| `~/.claude/rules/vmlx/caching.md`       | 5 couches KV détaillées, configs par profil (agent/RAG/chat), métriques                                      | `**/*vmlx*cache*`, `**/*kv*cache*`, `**/*prefix*cache*`                                       |
| `~/.claude/rules/vmlx/jang.md`          | Quantization JANG : profils, conversion, tradeoffs, interaction Smelt/caching                                | `**/*jangq*`, `**/*JANG_*`, `**/*.jangq`                                                      |
