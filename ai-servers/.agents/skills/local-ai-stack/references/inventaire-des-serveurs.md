## Inventaire des serveurs

Source de vérité = `~/ai-servers/servers.yaml` (lire avant toute affirmation). **18 entrées** gérées par aictl + **omlx** externe (brew, :8211). Ollama retiré (2026-07-06).

| Catégorie    | Serveur                   | Port      | Modèle / Notes                                                |
| ------------ | ------------------------- | --------- | ------------------------------------------------------------- |
| Gateway      | litellm-proxy             | :8092     | LiteLLM AI Gateway DB-backed, master key Keychain             |
| LLM externe  | **omlx**                  | **:8211** | Multi-modèles (Qwen3.6, Qwen3-Coder, Gemma4…), brew           |
| Vector store | litellm-pgvector          | :8093     | Sidecar OpenAI Vector Stores API, Postgres17 + pgvector       |
| Vector store | litellm-pgvector-openclaw | :8100     | Sidecar pgvector dédié OpenClaw                               |
| Embedding    | embedding                 | :8084     | Qwen3-Embedding-0.6B 1024D                                    |
| Reranker     | reranker                  | :8085     | BGE-reranker-v2-m3                                            |
| NER          | gliner                    | :8091     | GLiNER Biomed, PyTorch CPU                                    |
| OCR          | docling                   | :5010     | Docling                                                       |
| STT          | whisper-stt               | :2022     | Whisper large-v3-turbo (LoRA voix Michael)                    |
| TTS          | voxcpm-tts                | :8025     | VoxCPM2 Michael v7 MLX 8bit                                   |
| TTS          | voxcpm-openai-bridge      | :8883     | Pont OpenAI-compatible → OpenClaw TTS                         |
| Translation  | spark-translation (DGX)   | :6060     | NLLB-200 — migré sur DGX Spark 2026-07-10 (10.0.1.1/10.0.0.5) |
| VLM          | mlx-vlm-omni              | :8089     | Gemma 4 12B omni (démarrage manuel, contrôle RAM)             |
| App          | study-chat-bridge         | :8765     | Pont fiches concept-interactif                                |
| App          | litellm-config-sync       | —         | Sync config/UI LiteLLM                                        |
| App          | openclaw                  | :18789    | Gateway IntelliSoins                                          |
| App          | signal-api                | :8094     | Signal Messenger REST API (autostart off)                     |
| App          | signal-agent-router       | :8096     | Signal Agent Router                                           |

Config : `~/ai-servers/servers.yaml` (source de vérité). LaunchAgents : `~/Library/LaunchAgents/com.ai-servers.*`.

Backends MLX standalone (ports 8080–8088, kokoro, ollama) : retirés — voir `litellm-proxy/standby-models.yaml`.
