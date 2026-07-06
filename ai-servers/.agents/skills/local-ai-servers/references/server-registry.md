# Server Registry Reference

Source of truth: `~/ai-servers/servers.yaml`
Last synced from the previous global skill snapshot: 2026-06-08.

## Server Inventory

| ID                  | Name                                 | Category     | Port | Host      | Managed By | Requires Disk | Health Endpoint    |
| ------------------- | ------------------------------------ | ------------ | ---- | --------- | ---------- | ------------- | ------------------ |
| mlxcel              | mlxcel (Rust native MLX)             | llm          | 8097 | 127.0.0.1 | aictl      | No            | /v1/models         |
| medgemma-27b        | MedGemma 27B Text                    | llm          | 8080 | 127.0.0.1 | aictl      | No            | /v1/models         |
| medgemma-4b-vision  | MedGemma 4B Vision                   | vlm          | 8001 | 127.0.0.1 | aictl      | No            | /v1/models         |
| qwen3-email         | Qwen3-8B Email LoRA                  | llm          | 8081 | 127.0.0.1 | aictl      | Yes           | /v1/models         |
| nemotron-30b        | Nemotron 30B Tools                   | llm          | 8082 | 127.0.0.1 | aictl      | Yes           | /v1/models         |
| qwen3-merged        | Qwen3-8B Merged + Tools              | llm          | 8083 | 127.0.0.1 | aictl      | Yes           | /v1/models         |
| embedding           | Qwen3-Embedding-0.6B                 | embedding    | 8084 | 127.0.0.1 | aictl      | No            | /health            |
| reranker            | BGE-reranker-v2-m3                   | reranker     | 8085 | 127.0.0.1 | aictl      | No            | /health            |
| gliner              | GLiNER Biomed NER                    | ner          | 8091 | 127.0.0.1 | aictl      | No            | /health            |
| qwen35-35b          | Qwen3.5 35B MoE Agentic              | llm          | 8087 | 127.0.0.1 | aictl      | No            | /v1/models         |
| gemma3-4b           | Gemma 3 4B General                   | llm          | 8086 | 127.0.0.1 | aictl      | Yes           | /v1/models         |
| gemma4-12b          | Gemma 4 12B Instruct                 | llm          | 8098 | 127.0.0.1 | aictl      | Yes           | /v1/models         |
| docling             | Docling OCR/Extraction               | ocr          | 5010 | 127.0.0.1 | aictl      | No            | /health            |
| kokoro-tts          | Kokoro TTS                           | tts          | 8880 | 127.0.0.1 | aictl      | No            | /v1/models         |
| whisper-stt         | Whisper large-v3-turbo STT           | stt          | 2022 | 127.0.0.1 | aictl      | No            | /health            |
| translation         | NLLB-200 Traduction                  | translation  | 6060 | 127.0.0.1 | aictl      | No            | /health            |
| gemma4-e4b          | Gemma 4 E4B Multimodal               | vlm          | 8088 | 127.0.0.1 | aictl      | No            | /v1/models         |
| qwen35-9b-vision    | Qwen3.5-9B Vision + Tools            | vlm          | 8089 | 127.0.0.1 | aictl      | No            | /v1/models         |
| litellm-proxy       | LiteLLM Proxy (OpenAI gateway)       | llm          | 8092 | 127.0.0.1 | aictl      | No            | /health/liveliness |
| litellm-config-sync | LiteLLM Config/UI Sync               | app          | None | 127.0.0.1 | aictl      | No            | None               |
| litellm-pgvector    | LiteLLM PGVector sidecar             | vector_store | 8093 | 127.0.0.1 | aictl      | No            | /health            |
| signal-api          | Signal Messenger REST API            | app          | 8094 | 127.0.0.1 | aictl      | No            | /v1/health         |
| signal-agent-router | Signal Agent Router                  | app          | 8096 | 127.0.0.1 | aictl      | No            | /health            |
| omlx                | oMLX (multi-model, KV cache RAM+SSD) | llm          | 8211 | 127.0.0.1 | brew       | No            | /health            |

## Categories

| Category     | Servers                                                                                                   | Purpose                                                      |
| ------------ | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| llm          | mlxcel, medgemma-27b, qwen3-email, nemotron-30b, qwen3-merged, gemma3-4b, gemma4-12b, litellm-proxy, omlx | Text generation, chat, tools, proxy routing                  |
| vlm          | medgemma-4b-vision, gemma4-e4b, qwen35-9b-vision                                                          | Vision + language                                            |
| embedding    | embedding                                                                                                 | Vector embeddings (1024D) for pgvector RAG                   |
| reranker     | reranker                                                                                                  | Re-ranking search results                                    |
| ner          | gliner                                                                                                    | Biomedical NER for SQL/RAG pipelines                         |
| ocr          | docling                                                                                                   | Document OCR and extraction                                  |
| tts          | kokoro-tts                                                                                                | Text-to-speech                                               |
| stt          | whisper-stt                                                                                               | Speech-to-text                                               |
| translation  | translation                                                                                               | Neural machine translation FR/EN                             |
| app          | litellm-config-sync, signal-api, signal-agent-router                                                      | Utility apps, background sync services, and API integrations |
| vector_store | litellm-pgvector                                                                                          | Vector databases and database sidecars (e.g., pgvector)      |

## Disk Dependency: PRO-G40

External SSD containing large Hugging Face model caches.

Current `servers.yaml` marks `requires_disk: true` for qwen3-email,
nemotron-30b, qwen3-merged, gemma3-4b, and gemma4-12b. Launcher reality can differ, so
inspect launchers before making a current claim.

## API Compatibility

Most LLM/VLM servers expose OpenAI-compatible API endpoints:
`/v1/chat/completions` and `/v1/models`.

Specialized endpoints:

- embedding: `/v1/embeddings`
- reranker: `/v1/rerank`
- gliner: `/predict` and `/health`
- whisper-stt: `/v1/audio/transcriptions`
