## Continue VS Code — stack 100% local

Config `~/.continue/config.yaml` routée sur 4 ports locaux, zéro cloud.

| Rôle                | Port  | Modèle                    | Backend                   |
| ------------------- | ----- | ------------------------- | ------------------------- |
| autocomplete FIM    | :8000 | Qwen2.5-Coder-3B-bf16     | omlx                      |
| chat / edit / apply | :8089 | qwen3.5-9b-vision         | vllm-mlx (aictl)          |
| embed               | :8084 | Qwen/Qwen3-Embedding-0.6B | mlx-openai-server (aictl) |
| rerank              | :8085 | BAAI/bge-reranker-v2-m3   | mlx-openai-server (aictl) |

Note : bypass direct des ports (pas via proxy LiteLLM) pour latence minimale.
