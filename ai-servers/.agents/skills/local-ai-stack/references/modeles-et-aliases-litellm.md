## Modèles et aliases LiteLLM

`config.yaml` expose **~157 modèles live** via le proxy DB-backed (`curl :8092/v1/models`).

| model_name / alias                                                                       | Type                           |
| ---------------------------------------------------------------------------------------- | ------------------------------ |
| `general-local`, `Qwen3.6-35B-A3B-4bit`                                                  | LLM local via oMLX :8211       |
| `code-local`, `Qwen3-Coder-30B-A3B-Instruct-4bit`                                        | Code local via oMLX :8211      |
| `gemma4-12b`, `gemma4-12b-mlx`, `voice-local`                                            | Gemma 4 via oMLX :8211         |
| `qwen3-embedding` (1024D), `bge-reranker-v2-m3`                                          | Embedding :8084 / Rerank :8085 |
| `whisper-stt`                                                                            | STT :2022                      |
| `gpt-5.5`, `gpt-4o`                                                                      | Cloud OpenAI                   |
| `deepseek-v3.1`, `deepseek-r1`, `qwen3-235b`, `qwen3-coder-480b`, `glm-5.1`, `kimi-k2.6` | Together AI (cloud US)         |
| `claude-local-*`                                                                         | Aliases Claude Code → locaux   |
| `claude-together-*`, `claude-openai-*`                                                   | Aliases Claude Code → cloud    |
| `anthropic-claude-*`, `vertex-claude-*`                                                  | Anthropic API / Vertex via hub |

**Standby** (retirés de la config active, ports MLX morts) : `medgemma-27b`, `qwen3-email`, `nemotron-30b`, `qwen3-merged`, `qwen35-35b`, `gemma4-e4b`, `medgemma-4b-vision`, `gemma3-4b`, `vmlx-qwen36` — voir `litellm-proxy/standby-models.yaml`.

**Retiré** : `ollama-default` (Ollama supprimé 2026-07-06).

Backends locaux hors oMLX : démarrer via `aictl start <name>` avant appel direct.

**Together AI caveats** :

- Modèles de reasoning (`kimi-k2.6`, `deepseek-r1`) consomment des tokens en `reasoning_content` : prévoir `max_tokens` ≥ 80 sinon `content` revient vide.
- Voir `~/ai-servers/litellm-proxy/config.yaml` pour la liste complète.
