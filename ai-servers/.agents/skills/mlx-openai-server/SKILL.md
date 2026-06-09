---
name: mlx-openai-server

description: mlx-openai-server (cubist38/mlx-openai-server) — serveur OpenAI-compatible Apple Silicon, 6 types de modèles (lm, multimodal, image-gen, image-edit, embeddings, whisper), config YAML multi-modèle on-demand, multi-adapter LoRA (--lora-paths), 11+ parsers tool/reasoning, KV cache quantization (q4/q8), speculative decoding, image-gen/edit via mflux, Whisper, structured output. Charge on-demand sur fichiers mlx-openai-server ou servers.yaml.
paths:
  - "**/*mlx-openai-server*"
  - "**/*mlx_openai*"
  - "**/servers.yaml"
---

# mlx-openai-server

Serveur API OpenAI-compatible pour Apple Silicon par cubist38 — [GitHub](https://github.com/cubist38/mlx-openai-server). FastAPI + 6 backends MLX dans une seule interface. Version courante **v1.8.1 (2026-05-03)** (précédente : v1.8.0).

## Pourquoi ce serveur

Le seul serveur MLX qui combine sous la même interface :

- **6 model types** : `lm`, `multimodal`, `image-generation`, `image-edit`, `embeddings`, `whisper`
- **LoRA multi-adapter** (`--lora-paths` comma-separated avec `lora_scales`) — unique parmi les serveurs MLX courants
- **YAML multi-model** avec `on_demand` loading + `idle_timeout`
- **mflux integration** complète : Flux Schnell/Dev/Krea, Flux 2 Klein 4B/9B, Qwen-Image, Z-Image Turbo, FIBO, Flux Kontext (édition)

## Installation

```bash
python3.11 -m venv .venv
source .venv/bin/activate
uv pip install mlx-openai-server

# Whisper transcription requiert ffmpeg
brew install ffmpeg
```

**Requirements** : macOS Apple Silicon, Python **3.11+** (pas 3.12+).

> ⚠️ Conflits dépendances connus en Python 3.13/3.14 (resolution failures avec `outlines` et `torchvision`). Utiliser un venv Python 3.11 ou 3.12 dédié.

## Quick Start — par type de modèle

```bash
# Text LLM (Qwen3-Coder Next 4-bit)
mlx-openai-server launch \
  --model-type lm \
  --model-path mlx-community/Qwen3-Coder-Next-4bit \
  --reasoning-parser qwen3_moe \
  --tool-call-parser qwen3_coder

# Multimodal (vision/audio)
mlx-openai-server launch --model-type multimodal --model-path <mlx-vlm-model>

# Image generation
mlx-openai-server launch \
  --model-type image-generation \
  --model-path <flux-model> \
  --config-name flux-dev \
  --quantize 8

# Image editing (instruction-based)
mlx-openai-server launch \
  --model-type image-edit \
  --model-path <flux-or-qwen-edit-model> \
  --config-name flux-kontext-dev \
  --quantize 8

# Embeddings
mlx-openai-server launch --model-type embeddings --model-path <embedding-model>

# Whisper STT
mlx-openai-server launch --model-type whisper --model-path mlx-community/whisper-large-v3-mlx
```

Server à `http://localhost:8000/v1`. API key non-vide quelconque (ex: `not-needed`).

## Backends et endpoints

| Type               | Backend        | Endpoints                  |
| ------------------ | -------------- | -------------------------- |
| `lm`               | mlx-lm         | chat, responses            |
| `multimodal`       | mlx-vlm        | chat, responses            |
| `image-generation` | mflux          | `/v1/images/generations`   |
| `image-edit`       | mflux          | `/v1/images/edits`         |
| `embeddings`       | mlx-embeddings | `/v1/embeddings`           |
| `whisper`          | mlx-whisper    | `/v1/audio/transcriptions` |

`config-name` valeurs disponibles :

- **Génération** : `flux-schnell`, `flux-dev`, `flux-krea-dev`, `flux2-klein-4b`, `flux2-klein-9b`, `qwen-image`, `z-image-turbo`, `fibo`
- **Édition** : `flux-kontext-dev`, `flux2-klein-edit-4b`, `flux2-klein-edit-9b`, `qwen-image-edit`

## LoRA Multi-Adapter (unique parmi serveurs MLX)

```bash
# Single LoRA
mlx-openai-server launch --model-type lm --model-path <base> \
  --lora-paths /path/to/adapter1

# Multi-LoRA avec scales custom
mlx-openai-server launch --model-type lm --model-path <base> \
  --lora-paths /path/to/adapter1,/path/to/adapter2 \
  --lora-scales 1.0,0.5
```

C'est le serveur **idéal pour itération rapide pendant fine-tuning** (test plusieurs LoRA sans avoir à fuser).

## Tool Calling et Reasoning Parsers

```bash
mlx-openai-server launch --model-type lm --model-path <model> \
  --tool-call-parser qwen3_coder \
  --reasoning-parser qwen3_moe \
  --enable-auto-tool-choice
```

**Parsers supportés** : `qwen3`, `qwen3_5`, `qwen3_coder`, `qwen3_moe`, `qwen3_next`, `qwen3_vl`, `glm4_moe`, `harmony`, `minimax_m2`.

> 💡 Pour Qwen3.5-9B-MLX-4bit + Claude Code : `--tool-call-parser qwen3_coder` (format `<function=NAME>`), pas `qwen3` (format JSON `<tool_call>`). Cohérent avec la note mémoire vllm-mlx.

Message converters auto-détectés depuis le parser quand un converter compatible existe.

## Speculative Decoding (LM seulement)

```bash
mlx-openai-server launch --model-type lm \
  --model-path <main-model> \
  --draft-model-path <smaller-draft-model> \
  --num-draft-tokens 4
```

⚠️ Pas utilisé par le continuous batch path.

## Structured Output

OpenAI `response_format` JSON schema sur chat completions. Responses API supporte aussi `client.responses.parse()` avec Pydantic models.

## Multi-Model YAML

```bash
mlx-openai-server launch --config config.yaml
```

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  log_level: INFO

models:
  - model_path: mlx-community/MiniMax-M2.5-4bit
    model_type: lm
    served_model_name: minimax
    tool_call_parser: minimax_m2
    reasoning_parser: minimax_m2

  - model_path: black-forest-labs/FLUX.2-klein-4B
    model_type: image-generation
    served_model_name: flux2-klein-4b
    config_name: flux2-klein-4b
    quantize: 4
    on_demand: true
    on_demand_idle_timeout: 120
```

**Clés YAML importantes** : `model_path`, `model_type`, `served_model_name`, `context_length`, `prompt_cache_size`, `prompt_cache_max_bytes`, `prompt_cache_dir`, `batch_completion_size`, `batch_prefill_size`, `batch_prefill_step_size`, `kv_bits`, `kv_group_size`, `quantized_kv_start`, `default_max_tokens`, `on_demand`, `on_demand_idle_timeout`.

En multi-model mode, chaque modèle tourne dans un **subprocess séparé** — isole l'état MLX/Metal et évite les semaphore issues macOS.

## Long Context et Metal OOM

Symptôme typique :

```
libc++abi: terminating due to uncaught exception of type std::runtime_error:
[METAL] Command buffer execution failed: Internal Error (0000000e:Internal Error)
```

Config conservatrice à essayer :

```bash
mlx-openai-server launch --model-type lm --model-path <model> \
  --context-length 8192 \
  --decode-concurrency 4 \
  --prompt-concurrency 1 \
  --prefill-step-size 512 \
  --max-tokens 2048 \
  --prompt-cache-size 1 \
  --max-bytes 2147483648 \
  --kv-bits 4 \
  --kv-group-size 64 \
  --quantized-kv-start 0
```

**Ordre de tuning** :

1. Baisser `--prompt-concurrency` et `--prefill-step-size` (réduit prefill spikes)
2. Baisser `--decode-concurrency` (réduit KV caches actifs)
3. Baisser `--max-tokens`
4. Baisser `--prompt-cache-size`, set `--max-bytes`
5. `--kv-bits 4` pour les modèles supportés
6. Réduire `--context-length` en dernier recours

Pour gros modèles macOS 15+ : raise wired memory via `bash configure_mlx.sh`.

## CLI Options principales

| Option                 | Défaut          | Notes                              |
| ---------------------- | --------------- | ---------------------------------- |
| `--model-path`         | requis          | Local path ou HF repo              |
| `--model-type`         | `lm`            | 6 types listés ci-dessus           |
| `--served-model-name`  | model path      | Alias accepté en API               |
| `--context-length`     | model default   | LM/multimodal context length       |
| `--max-tokens`         | 100000          | Default si non précisé             |
| `--temperature`        | 1.0             |                                    |
| `--top-p`              | 1.0             |                                    |
| `--top-k`              | 20              |                                    |
| `--repetition-penalty` | 1.0             |                                    |
| `--config-name`        | model-dependent | Image model preset                 |
| `--quantize`           | unset           | Image: `4`, `8`, `16`              |
| `--decode-concurrency` | 32              | Max concurrent batch decode        |
| `--prompt-concurrency` | 8               | Max prompts prefill ensemble       |
| `--prefill-step-size`  | 2048            | Tokens par prefill step            |
| `--prompt-cache-size`  | 10              | Retained prompt KV cache entries   |
| `--max-bytes`          | unbounded       | Prompt KV cache byte budget        |
| `--prompt-cache-dir`   | temp dir        | Directory disk-backed prompt cache |
| `--kv-bits`            | unset           | `4` ou `8`                         |
| `--kv-group-size`      | 64              | KV quant group size                |
| `--quantized-kv-start` | 0               | Token step où KV quant commence    |
| `--draft-model-path`   | unset           | Speculative decoding               |
| `--num-draft-tokens`   | 2               | Draft tokens par step              |
| `--lora-paths`         | unset           | LoRA paths comma-separated         |
| `--lora-scales`        | unset           | LoRA scales comma-separated        |

## Bug connu : Gemma3Processor (MedGemma, Gemma 3 VLM)

**Deux bugs** quand on sert des modèles multimodaux Gemma 3 (ex: `medgemma-4b-it-4bit`) via mlx-openai-server (testé v1.1.2 jusqu'à v1.7.0+) :

1. `"Cannot use apply_chat_template because this processor does not have a chat template"` — Gemma3Processor n'embed pas le chat template.
   **Workaround** : passer `--chat-template-file` pointant vers le `chat_template.jinja` du modèle.

2. `"expand_dims(): incompatible function arguments... Invoked with types: NoneType, int"` — `create_inputs()` du serveur appelle `self.processor(text=[text], images=images, return_tensors="pt")` qui échoue sur le pipeline image processing de Gemma3Processor.
   **Aucun workaround connu**.

**Résolution** : utiliser **vllm-mlx** pour les modèles multimodaux Gemma 3. Le même modèle fonctionne parfaitement avec `mlx_vlm.generate()` direct et avec vllm-mlx. Exemple :

```bash
vllm-mlx serve mlx-community/medgemma-4b-it-4bit --port 8001 --host 127.0.0.1
```

## Examples (notebooks dans `examples/`)

| Domaine              | Notebooks                                                                                   |
| -------------------- | ------------------------------------------------------------------------------------------- |
| Text + Responses API | `responses_api.ipynb`, `simple_rag_demo.ipynb`                                              |
| Vision               | `vision_examples.ipynb`                                                                     |
| Audio                | `audio_examples.ipynb`, `transcription_examples.ipynb`                                      |
| Embeddings           | `embedding_examples.ipynb`, `lm_embeddings_examples.ipynb`, `vlm_embeddings_examples.ipynb` |
| Images               | `image_generations.ipynb`, `image_edit.ipynb`                                               |
| Structured outputs   | `structured_outputs_examples.ipynb`                                                         |

## Upgrade backends pour nouvelles architectures

```bash
uv pip install git+https://github.com/ml-explore/mlx-lm.git
uv pip install git+https://github.com/Blaizzy/mlx-vlm.git
uv pip install git+https://github.com/Blaizzy/mlx-embeddings.git
```

## Quand choisir mlx-openai-server

✅ **LoRA multi-adapter hot-load** — unique parmi serveurs MLX
✅ **Image gen + édition FLUX** — workflow complet (10 config-names)
✅ **Whisper transcription** locale dédiée
✅ **Multi-model YAML** avec on-demand + idle timeout
✅ **Mix multimodal/embeddings/audio** dans un seul serveur

❌ **Pas pour** : Gemma 3 multimodal (bug), Mamba/SSM, distributed multi-Mac, Ollama API native, Anthropic API native (OpenAI seulement) — voir vMLX, vllm-mlx, oMLX selon le besoin.

## License

MIT.

<citation>https://api.github.com/repos/cubist38/mlx-openai-server/releases — consulté 2026-05-29, release 2026-05-03</citation>
