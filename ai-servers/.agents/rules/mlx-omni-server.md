---
description: mlx-omni-server (madroidmaq/mlx-omni-server) — serveur d'inférence local Apple Silicon, dual API OpenAI (/v1/*) ET Anthropic (/anthropic/v1/*) sur le même port, auto-discovery zero-config depuis le cache HuggingFace, suite complète (chat tools/streaming/structured output, audio TTS+STT, image-gen, embeddings), function calling, thinking mode. Charge on-demand sur fichiers mlx-omni-server ou servers.yaml.
paths:
  - "**/*mlx-omni-server*"
  - "**/*mlx_omni*"
  - "**/servers.yaml"
---

# mlx-omni-server

Local AI inference server pour Apple Silicon par madroidmaq — [GitHub](https://github.com/madroidmaq/mlx-omni-server). Le seul serveur MLX qui expose **OpenAI ET Anthropic** sur le **même port avec auto-discovery zéro-config**.

**Version courante** : v0.5.3 (2026-05-09). Précédente : v0.5.2.

## Pourquoi ce serveur

| Force distinctive           | Détail                                                                          |
| --------------------------- | ------------------------------------------------------------------------------- |
| **Dual API simultanée**     | OpenAI à `/v1/*`, Anthropic à `/anthropic/v1/*` sur même port                   |
| **Auto-discovery HF cache** | Aucun `--model-path` requis — découvre les MLX models déjà téléchargés          |
| **Auto-download**           | Modèle non en cache ? Télécharge à la première requête                          |
| **Suite complète**          | Chat (tools, streaming, structured output) + TTS + STT + Image gen + Embeddings |

C'est le **drop-in le plus simple** des 6 serveurs MLX. Idéal prototypage rapide ou quand on alterne entre OpenAI et Anthropic SDKs.

## Installation

```bash
pip install mlx-omni-server
```

**Requirements** : Python 3.11+, Apple Silicon, MLX framework.

## Quick Start

```bash
# Démarrage par défaut (port 10240)
mlx-omni-server

# Port custom
mlx-omni-server --port 8000

# Debug logging
MLX_OMNI_LOG_LEVEL=debug mlx-omni-server

# Toutes options
mlx-omni-server --help
```

Pas de `--model-path` requis — on précise juste le modèle dans la requête API. Si pas en cache local, téléchargement auto.

## Connexion OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:10240/v1",
    api_key="not-needed"
)

response = client.chat.completions.create(
    model="mlx-community/gemma-3-1b-it-4bit-DWQ",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
```

## Connexion Anthropic SDK

```python
import anthropic

client = anthropic.Anthropic(
    base_url="http://localhost:10240/anthropic",
    api_key="not-needed"
)

message = client.messages.create(
    model="mlx-community/gemma-3-1b-it-4bit-DWQ",
    max_tokens=1000,
    messages=[{"role": "user", "content": "Hello!"}]
)
print(message.content[0].text)
```

## Endpoints supportés

### OpenAI compatible (`/v1/*`)

| Endpoint                   | Feature                                       |
| -------------------------- | --------------------------------------------- |
| `/v1/chat/completions`     | Chat avec tools, streaming, structured output |
| `/v1/audio/speech`         | Text-to-Speech                                |
| `/v1/audio/transcriptions` | Speech-to-Text (Whisper)                      |
| `/v1/images/generations`   | Image generation (FLUX)                       |
| `/v1/embeddings`           | Text embeddings                               |
| `/v1/models`               | Model management                              |

### Anthropic compatible (`/anthropic/v1/*`)

| Endpoint                 | Feature                                           |
| ------------------------ | ------------------------------------------------- |
| `/anthropic/v1/messages` | Messages avec tools, streaming, **thinking mode** |
| `/anthropic/v1/models`   | Model listing avec pagination                     |

> ⚠️ Pas le même chemin que vMLX/vllm-mlx (qui exposent Anthropic à `/v1/messages`). Ici c'est `/anthropic/v1/messages`. Important pour configurer Claude Code correctement.

## Features avancées

| Feature             | Statut                                  |
| ------------------- | --------------------------------------- |
| Function calling    | ✅ avec parsers model-specific          |
| Real-time streaming | ✅ (OpenAI + Anthropic)                 |
| Structured output   | ✅ JSON schema validation               |
| Extended reasoning  | ✅ Thinking mode pour modèles supportés |
| Auto-discovery      | ✅ MLX models dans HF cache             |
| On-demand loading   | ✅ Intelligent caching                  |
| Auto-download       | ✅ Si modèle non en cache               |

## Audio (TTS + STT)

Stack audio supportée :

- **F5-TTS** (text-to-speech)
- **Whisper** (speech-to-text via mlx-whisper)

## Image Generation

FLUX via intégration mlx-vlm/mflux. Voir endpoints `/v1/images/generations`.

## Configuration

Tout via env vars et CLI :

```bash
# Variable env utiles
MLX_OMNI_LOG_LEVEL=debug    # Niveau de log
mlx-omni-server --port 8000 # Port custom
```

Pas de fichier de config YAML/JSON — tout passe par les requêtes API.

## Pré-télécharger un modèle

Pour éviter le délai du premier appel :

```bash
huggingface-cli download mlx-community/gemma-3-1b-it-4bit-DWQ
```

Ensuite `mlx-omni-server` le détectera automatiquement.

## Quand choisir mlx-omni-server

✅ **Dual API simultanée** OpenAI + Anthropic sans config
✅ **Prototypage rapide** — zéro flag, juste lancer
✅ **Auto-discovery** des modèles HF déjà cachés
✅ **Mix utilisations** : chat, TTS, STT, image, embeddings dans un seul serveur

❌ **Pas pour** :

- Production agentic long-running (pas de prefix cache mesuré, pas de KV quant) — voir oMLX, vMLX
- Multi-user batch throughput — voir vllm-mlx
- LoRA multi-adapter — voir mlx-openai-server
- Mamba/SSM, distributed multi-Mac — voir vMLX
- Per-model fine config (context length, KV bits) — voir mlx-openai-server YAML

## Configurer Claude Code

```bash
# Path différent — `/anthropic` dans le base URL
export ANTHROPIC_BASE_URL=http://127.0.0.1:10240/anthropic
export ANTHROPIC_AUTH_TOKEN=local
export ANTHROPIC_API_KEY=local
claude --model mlx-community/gemma-3-1b-it-4bit-DWQ
```

⚠️ Path `/anthropic` (pas juste racine comme vMLX/vllm-mlx).

## Documentation

- [OpenAI API Guide](https://github.com/madroidmaq/mlx-omni-server/blob/main/docs/openai-api.md)
- [Anthropic API Guide](https://github.com/madroidmaq/mlx-omni-server/blob/main/docs/anthropic-api.md)
- Examples : `examples/` du repo

## Crédits & licence

Built sur MLX (Apple), FastAPI, MLX-LM. Pas affilié à OpenAI, Anthropic ou Apple. Licence MIT.

<citation>https://api.github.com/repos/madroidmaq/mlx-omni-server/releases — consulté 2026-05-29, release 2026-05-09</citation>
