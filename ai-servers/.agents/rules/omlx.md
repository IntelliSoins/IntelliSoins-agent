---
description: oMLX (jundot/omlx) — serveur d'inférence MLX local Apple Silicon : continuous batching, tiered KV cache (RAM chaud + SSD froid persistant aux restarts), backend Claude Code/Codex, multi-modèle (LRU/pinning/TTL), VLM+OCR, embeddings+rerankers, API OpenAI+Anthropic native, menubar macOS. Charge on-demand sur fichiers omlx ou servers.yaml.
paths:
  - "**/*omlx*"
  - "**/servers.yaml"
  - "~/ai-servers/**"
---

# oMLX

Serveur d'inférence LLM pour Apple Silicon par Jun Kim — [omlx.ai](https://omlx.ai) · [jundot/omlx](https://github.com/jundot/omlx).
Continuous batching + tiered KV caching + optimisation Claude Code, géré depuis la barre de menu.

**Version courante** : v0.3.12 (2026-05-27), stable. Voir « Historique upstream » plus bas pour le détail des features livrées jusqu'à v0.3.9rc1.

**Origine** : forké de vllm-mlx v0.1.0, évolué massivement (multi-model serving, tiered cache, VLM avec paged cache complet, admin panel, app macOS).

## Pourquoi oMLX est conçu pour l'agentique Claude Code

Le README positionne explicitement oMLX pour les gros contextes agentiques : cache KV persistant entre RAM et SSD, réutilisation du contexte après changement de conversation ou redémarrage, et optimisations dédiées Claude Code.

**Claude Code Optimization** est une feature explicite (section nommée dans le README) :

- Context scaling support pour exécuter de petits modèles avec Claude Code
- Token count rescaling pour que l'auto-compact se déclenche au bon moment
- SSE keep-alive prévient les timeouts pendant les longs prefills

## Installation

### macOS App (recommandé pour usage interactif)

Téléchargement DMG depuis [Releases](https://github.com/jundot/omlx/releases). Drag-to-Applications, in-app auto-update intégré. **Note** : l'app n'installe pas la CLI `omlx` — pour le terminal, passer par Homebrew ou source.

### Homebrew (recommandé pour usage CLI)

```bash
brew tap jundot/omlx https://github.com/jundot/omlx
brew install omlx

# Service background avec auto-restart
brew services start omlx

# Optional: MCP tool support
/opt/homebrew/opt/omlx/libexec/bin/pip install mcp
```

### Source

```bash
git clone https://github.com/jundot/omlx.git
cd omlx
pip install -e .          # Core
pip install -e ".[mcp]"   # Avec MCP
```

**Requirements** : macOS 15.0+ (Sequoia), Python 3.10+ selon README, Apple Silicon M1+. Pour l'installation depuis source/dev, préférer Python 3.11+ car `pyproject.toml` déclare `requires-python = ">=3.11"`.

## Quick Start

```bash
# CLI — découverte auto des modèles dans un répertoire
omlx serve --model-dir ~/models

# Avec SSD cache + hot cache 20% RAM
omlx serve --model-dir ~/models \
  --paged-ssd-cache-dir ~/.omlx/cache \
  --hot-cache-max-size 20%
```

Server à `http://localhost:8000/v1` (OpenAI + Anthropic compatible). Admin dashboard à `http://localhost:8000/admin` (chat intégré, monitoring, model management, benchmark).

### Connecter Claude Code, Codex et OpenClaw

Via l'admin dashboard : section **Integrations** propose OpenClaw, OpenCode, Codex, Hermes Agent, Copilot et Pi en **1-click setup** (zéro édition manuelle de config).

Via la CLI, utiliser le launch picker quand disponible :

```bash
omlx launch claude
omlx launch codex
omlx launch openclaw
omlx launch copilot
```

Depuis v0.3.9rc1, les arguments supplémentaires sont transmis à `codex` et `claude`, ce qui permet de garder les flags habituels de ces CLIs.

Configuration manuelle (équivalent vllm-mlx) :

```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:8000
export ANTHROPIC_AUTH_TOKEN=local
export ANTHROPIC_API_KEY=local
claude --model <model-name>
```

## Tiered KV Cache (Hot + Cold)

Block-based KV cache inspiré de vLLM avec prefix sharing et Copy-on-Write, étalé sur deux tiers :

| Tier           | Stockage               | Comportement                                                                                                                                                              |
| -------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Hot (RAM)**  | In-memory, write-back  | Blocs fréquents, accès rapide                                                                                                                                             |
| **Cold (SSD)** | Safetensors sur disque | Quand hot se remplit, offload vers SSD. Sur prochaine requête avec prefix matching, restauration **depuis disque** au lieu de recomputer — **survit aux restart serveur** |

### Performance mesurée

| Scénario                 | TTFT     | Speedup |
| ------------------------ | -------- | ------- |
| 8K cold prefill (M1 Max) | 49s      | —       |
| 8K SSD cache hit         | **1.7s** | **29×** |

Pour des sessions agent longues avec gros system prompts répétés, c'est _le_ cas d'usage. Élimine 30-90s de TTFT à chaque restart.

## Continuous Batching

Géré via `mlx-lm` BatchGenerator. Concurrent requests configurable :

```bash
omlx serve --model-dir ~/models --max-concurrent-requests 16  # défaut: 8
```

## Multi-Model Serving

Charger LLMs, VLMs, embedding models et rerankers dans le même serveur, avec contrôles automatiques + manuels :

| Mécanisme                      | Usage                                                                       |
| ------------------------------ | --------------------------------------------------------------------------- |
| **LRU eviction**               | Modèles least-recently-used évincés automatiquement quand RAM se remplit    |
| **Manual load/unload**         | Status badges interactifs dans admin panel                                  |
| **Model pinning**              | Pin un modèle pour qu'il reste toujours chargé (ex: ton modèle Claude Code) |
| **Per-model TTL**              | Auto-unload après période d'inactivité                                      |
| **Process memory enforcement** | Limite totale (défaut: RAM - 8 GB) prévient OOM système                     |

### Per-Model Settings (live, sans restart)

Sampling params, chat template kwargs, TTL, alias, type override (LLM vs VLM) — tout configurable depuis admin panel, changements appliqués immédiatement.

- **Model alias** : nom API custom. `/v1/models` retourne l'alias, requêtes acceptent alias et nom de répertoire.
- **Type override** : forcer LLM ou VLM indépendamment de l'auto-detection.

## Vision-Language Models + OCR

VLMs avec **continuous batching et tiered KV cache complet** (rare parmi les serveurs MLX). Multi-image chat, base64/URL/file inputs, tool calling avec contexte vision.

OCR auto-détectés avec prompts optimisés :

- DeepSeek-OCR
- DOTS-OCR
- GLM-OCR

## Tool Calling

Tool parsers via `mlx-lm` (auto-détectés selon famille) :

| Famille               | Format                           |
| --------------------- | -------------------------------- |
| Llama, Qwen, DeepSeek | JSON `<tool_call>`               |
| Qwen3.5 Series        | XML `<function=...>`             |
| Gemma                 | `<start_function_call>`          |
| GLM (4.7, 5)          | `<arg_key>/<arg_value>` XML      |
| MiniMax               | Namespaced `<minimax:tool_call>` |
| Mistral               | `[TOOL_CALLS]`                   |
| Kimi K2               | `<\|tool_calls_section_begin\|>` |
| Longcat               | `<longcat_tool_call>`            |

Streaming tool-enabled : texte assistant émis incrémentalement, control markup tool-call supprimé du contenu visible, structured tool calls émis après parse complet.

**MCP** : config via `--mcp-config mcp.json`. Requiert install optionnelle (`pip install mcp` après brew install). Endpoint `/v1/mcp/execute` accepte `tool` et `tool_name`.

## Structured Output

JSON Schema validation native. Pour les grammaires/regex strictes, installer l'extra optionnel `grammar` (`xgrammar`) si le build local le fournit.

## API Compatibility

Drop-in replacement OpenAI + Anthropic. Streaming usage stats (`stream_options.include_usage`), Anthropic adaptive thinking, vision inputs (base64 + URL), préservation des blocs reasoning de la Responses API à travers les allers-retours tool-call.

| Endpoint                        | Description                                        |
| ------------------------------- | -------------------------------------------------- |
| `POST /v1/chat/completions`     | OpenAI Chat Completions (streaming)                |
| `POST /v1/completions`          | Text completions (streaming)                       |
| `POST /v1/messages`             | **Anthropic Messages API**                         |
| `POST /v1/embeddings`           | Text embeddings                                    |
| `POST /v1/rerank`               | Document reranking                                 |
| `POST /v1/audio/transcriptions` | Transcription audio (`word_timestamps` disponible) |
| `POST /v1/mcp/execute`          | Exécution d'outil MCP                              |
| `GET /v1/models`                | List available models                              |

## Modèles supportés

Pointer `--model-dir` vers un répertoire avec sous-dossiers MLX. Organisation à 2 niveaux supportée (`mlx-community/model-name/`).

| Type      | Modèles                                         |
| --------- | ----------------------------------------------- |
| LLM       | Tout modèle supporté par mlx-lm                 |
| VLM       | Qwen3.5 Series, GLM-4V, Pixtral, autres mlx-vlm |
| OCR       | DeepSeek-OCR, DOTS-OCR, GLM-OCR                 |
| Embedding | BERT, BGE-M3, ModernBERT                        |
| Reranker  | ModernBERT, XLM-RoBERTa                         |

Auto-détection par type. Téléchargement direct depuis admin dashboard (Model Downloader avec browse cards HuggingFace, taille fichiers, 1-click download).

## CLI Configuration

```bash
# Memory limits
omlx serve --model-dir ~/models \
  --max-model-memory 32GB \
  --max-process-memory 80%

# Tiered cache
omlx serve --model-dir ~/models \
  --paged-ssd-cache-dir ~/.omlx/cache \
  --hot-cache-max-size 20%

# Concurrency
omlx serve --model-dir ~/models --max-concurrent-requests 16

# MCP tools
omlx serve --model-dir ~/models --mcp-config mcp.json

# HuggingFace mirror (régions restreintes)
omlx serve --model-dir ~/models --hf-endpoint https://hf-mirror.com

# Auth
omlx serve --model-dir ~/models --api-key your-secret-key
```

Settings persistent dans `~/.omlx/settings.json`. CLI flags ont précédence. Tout configurable aussi via admin panel `/admin`.

## Homebrew Service

```bash
brew services start omlx    # auto-restart on crash
brew services stop omlx
brew services restart omlx
brew services info omlx
```

Logs :

- Service (stdout/stderr) : `$(brew --prefix)/var/log/omlx.log`
- Server (structured) : `~/.omlx/logs/server.log`

Variables d'env : `OMLX_MODEL_DIR`, `OMLX_PORT`. Défauts : `~/.omlx/models`, port 8000.

## Architecture (résumé)

```
FastAPI Server (OpenAI / Anthropic API)
├── EnginePool (LRU eviction, TTL, manual load/unload)
│   ├── BatchedEngine (LLMs, continuous batching)
│   ├── VLMEngine
│   ├── EmbeddingEngine
│   └── RerankerEngine
├── ProcessMemoryEnforcer (limite totale, TTL checks)
├── Scheduler (FCFS, configurable concurrency)
│   └── mlx-lm BatchGenerator
└── Cache Stack
    ├── PagedCacheManager (GPU, block-based, CoW, prefix sharing)
    ├── Hot Cache (in-memory, write-back)
    └── PagedSSDCacheManager (SSD cold tier, safetensors)
```

## Admin Dashboard

Web UI à `/admin` :

- Real-time monitoring (modèles chargés, RAM, requests)
- Model management (load, unload, pin, TTL)
- Chat intégré avec n'importe quel modèle chargé (history, model switching, dark mode, reasoning output, image upload, multi-tasking — plusieurs chats parallèles)
- Performance benchmark 1-click (PP + TG tok/s, prefix cache hit testing)
- Model downloader HuggingFace
- Integrations setup (OpenClaw, OpenCode, Codex, Hermes Agent, Copilot, Pi)
- Multi-langue : English, Korean, Japanese, Chinese, French, Russian
- CDN deps vendored = full offline operation

## Menubar App

Native PyObjC (pas Electron). Persistent serving stats (survit aux restart), auto-restart on crash, in-app auto-update.

## vs autres serveurs MLX (focus agentic)

| Critère                          |      oMLX       |        vMLX         |       vllm-mlx        |
| -------------------------------- | :-------------: | :-----------------: | :-------------------: |
| Hot+Cold KV cache survit restart |    ✅ unique    |     ✅ L2 disk      |          ❌           |
| Claude Code-specific tweaks      |  ✅ explicite   |         ❌          |    ⚠️ ThinkRouter     |
| LoRA hot-load                    |       ✅        |  ❌ panel UI only   | ❌ fusion obligatoire |
| Multi-model LRU/pinning/TTL      |   ✅ raffiné    |   ✅ via gateway    |          ❌           |
| Tool parsers                     |  mlx-lm + MCP   |      13 natifs      |       16 natifs       |
| Architectures supportées         | mlx-lm standard |  50+ (Mamba, JANG)  |          30+          |
| KV quant q4/q8                   |       ❌        |         ✅          |          ✅           |
| Speculative decoding             |       ❌        |         ✅          |        ✅ MTP         |
| Image gen                        |       ❌        |         ❌          |          ❌           |
| Distributed multi-Mac            |       ❌        |         ✅          |          ❌           |
| Anthropic API native             |       ✅        |         ✅          |     ✅ (v0.2.8+)      |
| GUI                              |  menubar + web  | MLX Studio Electron |       CLI only        |

## Quand choisir oMLX

✅ **Coding agentic Claude Code** — c'est son use case principal, conçu pour ça
✅ **Restart fréquent du serveur** — SSD cache reload context en 1.7s vs 49s
✅ **Multi-modèles avec memory pressure** — LRU + pinning + TTL gèrent finement
✅ **Préférence GUI** — menubar + admin web complets, zéro terminal
✅ **LoRA hot-load testing**
✅ **OCR auto-détecté** — DeepSeek-OCR, DOTS-OCR, GLM-OCR

❌ **Pas pour** : image generation (FLUX), Mamba/SSM hybrids, distributed multi-Mac, JANG quantization, MTP speculative — voir vMLX ou vllm-mlx.

## Acknowledgments

oMLX est dérivé de vllm-mlx v0.1.0, étendu massivement avec multi-model serving, tiered cache, VLM avec paged cache complet, admin panel, et menubar app. Build sur mlx-lm, mlx-vlm, mlx-embeddings, dflash-mlx, venvstacks (app bundling).

## Historique upstream (features livrées jusqu'à v0.3.9rc1, 2026-05-19)

`v0.3.9rc1` (2026-05-19) fut un jalon RC ; la branche stable courante est **v0.3.12 (2026-05-27)**. Features apparues à ce jalon, conservées et toujours valides :

- **Memory management bas niveau** : enforcer basé sur `phys_footprint`, admission control pendant prefill, eviction hot-cache race corrigée, preload SSD → hot parallélisé, hit-rate cache par modèle observable, barre mémoire temps réel dans l'admin.
- **Chunked prefill** : long prefill découpé par scheduler step pour ne pas bloquer les decodes concurrents ; off par défaut, activable depuis admin.
- **Chat multi-tasking** : plusieurs chats parallèles dans l'admin et correction des réponses streamées qui pouvaient atterrir dans le mauvais chat.
- **Responses API reasoning** : préservation des blocs reasoning à travers les allers-retours tool-call.
- **Intégrations agentiques** : Hermes Agent quick launch, Copilot dans `omlx launch`, et forwarding d'arguments supplémentaires vers `omlx launch codex` et `omlx launch claude`.
- **MCP** : `/v1/mcp/execute` accepte `tool` et `tool_name`.
- **Audio transcription** : `word_timestamps` disponible sur `/v1/audio/transcriptions`.
- **DFlash / Gemma 4** : dflash-mlx bump v0.1.7, parsing gemma4 channel markers, nouveaux settings `draft_window_size`, `draft_sink_size`, `verify_mode`.
- **Admin UX** : Browse Models sortable, layout mobile amélioré, filtre minimal dans le log viewer, bouton restart déplacé près du Save.

Suivre [jundot/omlx/releases](https://github.com/jundot/omlx/releases) pour les deltas postérieurs à v0.3.12.

## License

Apache 2.0.

<citation>https://api.github.com/repos/jundot/omlx/releases — consulté 2026-05-29, release 2026-05-27</citation>
