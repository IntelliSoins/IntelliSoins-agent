## Inventaire des serveurs

Source de vérité = `~/ai-servers/servers.yaml` (lire avant toute affirmation). 21 entrées gérées par aictl + 2 externes brew (omlx :8000, Ollama). vMLX :8002 tourne via vMLX.app (ni aictl ni brew), routé par LiteLLM.

| Catégorie    | Serveur             | Port      | Modèle / Notes                                                    |
| ------------ | ------------------- | --------- | ----------------------------------------------------------------- |
| Gateway      | litellm-proxy       | :8092     | LiteLLM AI Gateway DB-backed, master key Keychain                 |
| Vector store | litellm-pgvector    | :8093     | Sidecar OpenAI Vector Stores API, Postgres17 + pgvector           |
| LLM          | medgemma-27b        | :8080     | MedGemma 27B (TurboQuant V2 3-bit actif)                          |
| LLM          | qwen3-email         | :8081     | Qwen3 email                                                       |
| LLM          | nemotron-30b        | :8082     | Nemotron 30B (**PRO-G40 strict**)                                 |
| LLM          | qwen3-merged        | :8083     | Qwen3 merged                                                      |
| LLM          | gemma3-4b           | :8086     | Gemma 3 4B                                                        |
| LLM          | qwen35-35b          | :8087     | Qwen3.5 35B MoE agentic                                           |
| LLM externe  | **omlx**            | **:8000** | multi-modèles (Qwen2.5-Coder-3B FIM…), KV cache RAM+SSD, brew     |
| LLM          | **vMLX**            | **:8002** | Qwen3.6-35B-A3B-JANGTQ reasoning MoE, vMLX.app (déplacé de :8000) |
| LLM externe  | ollama              | :11434    | Ollama, brew services                                             |
| VLM          | medgemma-4b-vision  | :8001     | MedGemma 4B vision                                                |
| VLM          | gemma4-e4b          | :8088     | Gemma 4 E4B multimodal                                            |
| VLM          | qwen35-9b-vision    | :8089     | Qwen3.5-9B Vision + Tools (backend chat Continue / vllm-mlx)      |
| Embedding    | embedding           | **:8084** | Qwen3-Embedding-0.6B 1024D (**PRO-G40 strict**)                   |
| Reranker     | reranker            | **:8085** | BGE-reranker-v2-m3 (**PRO-G40 strict**)                           |
| NER          | gliner              | :8091     | GLiNER Biomed, PyTorch CPU                                        |
| OCR          | docling             | :5010     | Docling                                                           |
| STT          | whisper-stt         | :2022     | Whisper large-v3-turbo, MLX                                       |
| TTS          | kokoro-tts          | :8880     | Kokoro TTS                                                        |
| Translation  | translation         | :6060     | NLLB-200                                                          |
| App          | litellm-config-sync | —         | Sync config/UI LiteLLM (`litellm_config_sync.py`, autostart)      |
| App          | signal-api          | :8094     | Signal Messenger REST API                                         |
| App          | signal-agent-router | :8096     | Signal Agent Router                                               |

Config : `~/ai-servers/servers.yaml` (source de vérité). LaunchAgents : `~/Library/LaunchAgents/com.ai-servers.*`.
