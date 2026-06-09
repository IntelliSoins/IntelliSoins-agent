## Skills & rules associés

- `intellisoins-infrastructure:local-ai-servers` — gestion aictl + servers.yaml
- `intellisoins-litellm:*` — 9 skills LiteLLM (proxy-setup, config-yaml, routing, cache, budgets, etc.)
- `intellisoins-mlx:*` — 50+ skills MLX (modèles spécifiques, fine-tuning, etc.)
- **Rules moteurs d'inférence** (converties des skills 2026-05-24) : `vmlx.md`, `vllm-mlx.md` (backend chat `:8089`), `vllm-metal.md`, `turboquant-mlx.md` (KV compression, actif sur medgemma-27b `:8080`) — backends MLX de cette stack. `vllm-omni.md` existe aussi mais cible GPU/NPU Linux → **hors stack Mac**.
- `intellisoins-architecture-health:health-check` — monitoring stack
