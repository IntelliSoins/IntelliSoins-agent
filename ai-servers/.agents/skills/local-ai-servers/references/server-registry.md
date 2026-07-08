# Server Registry Reference

Source of truth: `~/ai-servers/servers.yaml`
Last synced: 2026-07-06 (consolidation oMLX :8211 + LiteLLM :8092).

## Server Inventory

| ID                        | Name                                 | Category     | Port  | Host      | Managed By | Autostart | Health Endpoint    |
| ------------------------- | ------------------------------------ | ------------ | ----- | --------- | ---------- | --------- | ------------------ |
| embedding                 | Qwen3-Embedding-0.6B                 | embedding    | 8084  | 127.0.0.1 | aictl      | Yes       | /health            |
| reranker                  | BGE-reranker-v2-m3                   | reranker     | 8085  | 127.0.0.1 | aictl      | Yes       | /health            |
| gliner                    | GLiNER Biomed NER                    | ner          | 8091  | 127.0.0.1 | aictl      | Yes       | /health            |
| docling                   | Docling OCR/Extraction               | ocr          | 5010  | 127.0.0.1 | aictl      | Yes       | /health            |
| voxcpm-tts                | VoxCPM2 Michael v7 (MLX 8bit)        | tts          | 8025  | 127.0.0.1 | aictl      | Yes       | /v1/models         |
| voxcpm-openai-bridge      | VoxCPM OpenAI bridge (OpenClaw TTS)  | tts          | 8883  | 127.0.0.1 | aictl      | Yes       | /health            |
| whisper-stt               | Whisper large-v3-turbo STT           | stt          | 2022  | 127.0.0.1 | aictl      | Yes       | /health            |
| translation               | NLLB-200 Traduction                  | translation  | 6060  | 127.0.0.1 | aictl      | Yes       | /health            |
| litellm-proxy             | LiteLLM Proxy (OpenAI gateway)       | llm          | 8092  | 127.0.0.1 | aictl      | No        | /health/liveliness |
| study-chat-bridge         | Pont d'étude concept-interactif      | app          | 8765  | 127.0.0.1 | aictl      | Yes       | /health            |
| litellm-config-sync       | LiteLLM Config/UI Sync               | app          | None  | 127.0.0.1 | aictl      | Yes       | None               |
| litellm-pgvector          | LiteLLM PGVector sidecar             | vector_store | 8093  | 127.0.0.1 | aictl      | Yes       | /health            |
| litellm-pgvector-openclaw | LiteLLM PGVector sidecar (OpenClaw)  | vector_store | 8100  | 127.0.0.1 | aictl      | Yes       | /health            |
| signal-api                | Signal Messenger REST API            | app          | 8094  | 127.0.0.1 | aictl      | No        | /v1/health         |
| signal-agent-router       | Signal Agent Router                  | app          | 8096  | 127.0.0.1 | aictl      | No        | /health            |
| openclaw                  | OpenClaw (IntelliSoins Gateway)      | app          | 18789 | 127.0.0.1 | aictl      | Yes       | /healthz           |
| mlx-vlm-omni              | gemma-4-12B omni (mlx-vlm)           | vlm          | 8089  | 127.0.0.1 | aictl      | Yes       | /health            |
| omlx                      | oMLX (multi-model, KV cache RAM+SSD) | llm          | 8211  | 127.0.0.1 | brew       | brew      | /health            |

## Categories

| Category     | Servers                                                                           | Purpose                                       |
| ------------ | --------------------------------------------------------------------------------- | --------------------------------------------- |
| llm          | litellm-proxy, omlx                                                               | Text generation, hub routing, multi-model MLX |
| vlm          | mlx-vlm-omni                                                                      | Agent vocal (autostart, APC + draft MTP)      |
| embedding    | embedding                                                                         | Vector embeddings (1024D) for pgvector RAG    |
| reranker     | reranker                                                                          | Re-ranking search results                     |
| ner          | gliner                                                                            | Biomedical NER for SQL/RAG pipelines          |
| ocr          | docling                                                                           | Document OCR and extraction                   |
| tts          | voxcpm-tts, voxcpm-openai-bridge                                                  | Text-to-speech                                |
| stt          | whisper-stt                                                                       | Speech-to-text                                |
| translation  | translation                                                                       | Neural machine translation FR/EN              |
| app          | study-chat-bridge, litellm-config-sync, signal-api, signal-agent-router, openclaw | Utility apps and gateway                      |
| vector_store | litellm-pgvector, litellm-pgvector-openclaw                                       | pgvector sidecars                             |

## Retired Standalone MLX Backends

The following were removed from `servers.yaml` (2026-07-06). LLM/VLM routing goes through **oMLX :8211** or **LiteLLM :8092**. Re-entry rules: `litellm-proxy/standby-models.yaml`.

| Former ID    | Port  | Successor                             |
| ------------ | ----- | ------------------------------------- |
| medgemma-27b | 8080  | standby / oMLX on demand              |
| qwen3-email  | 8081  | standby                               |
| nemotron-30b | 8082  | standby                               |
| qwen3-merged | 8083  | standby                               |
| gemma3-4b    | 8086  | standby                               |
| qwen35-35b   | 8087  | `Qwen3.6-35B-A3B-CP-lmhead8` via oMLX |
| gemma4-e4b   | 8088  | `gemma4-12b` via oMLX                 |
| gemma4-12b   | 8098  | `gemma4-12b` via oMLX                 |
| kokoro-tts   | 8880  | voxcpm-tts :8025                      |
| ollama       | 11434 | **removed** (2026-07-06)              |

## API Compatibility

Most MLX/OpenAI-compatible servers expose `/v1/chat/completions` and `/v1/models`.
Health checks vary by server — see `health_endpoint` in `servers.yaml`.
Prefer routing through LiteLLM `:8092` for spend tracking, aliases, and fallbacks.
