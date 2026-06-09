## Modèles et aliases LiteLLM

`config.yaml` = **49 `model_name`** statiques ; le proxy DB-backed expose **~63 live** (`curl :8092/v1/models` — l'écart = entrées ajoutées via l'Admin UI).

| model_name                                                                               | Type                             |
| ---------------------------------------------------------------------------------------- | -------------------------------- |
| `gpt-5.5`, `gpt-4o`                                                                      | Cloud OpenAI                     |
| `medgemma-27b`, `qwen3-email`, `nemotron-30b`, `qwen3-merged`, `qwen35-35b`              | LLM MLX                          |
| `medgemma-4b-vision`, `gemma3-4b`, `gemma4-e4b`, `qwen35-9b-vision`                      | VLM MLX                          |
| `omlx-coder` (:8000), `vmlx-qwen36` (:8002)                                              | oMLX / vMLX locaux               |
| `ollama-default`                                                                         | Ollama brew                      |
| `qwen3-embedding` (1024D), `bge-reranker-v2-m3`                                          | Embedding / Rerank               |
| `whisper-stt`, `kokoro-tts`                                                              | Audio                            |
| `deepseek-v3.1`, `deepseek-r1`, `qwen3-235b`, `qwen3-coder-480b`, `glm-5.1`, `kimi-k2.6` | Together AI (cloud US)           |
| `claude-local-*`                                                                         | Aliases Claude Code → MLX locaux |
| `claude-together-*`, `claude-openai-*`                                                   | Aliases Claude Code → cloud      |
| `anthropic-claude-*`, `claude-opus-4-8[1m]`, `claude-opus-4-7[1m]`                       | OAuth Max forwarding (pattern B) |

Backends MLX **DOWN par défaut**. Avant d'appeler : `aictl start <name>`.

**Together AI caveats** :

- Modèles de reasoning (`kimi-k2.6`, `deepseek-r1`) consomment des tokens en `reasoning_content` : prévoir `max_tokens` ≥ 80 sinon `content` revient vide.
- 6/6 modèles testés OK en serverless (Ottawa retourné). Voir `~/ai-servers/litellm-proxy/config.yaml:107-138`.
