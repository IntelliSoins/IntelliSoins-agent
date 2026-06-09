---
name: local-ai-stack
description: Stack AI/ML personnelle Michael Ahern, installée nativement sur le disque (Apple Silicon M3 Max via Homebrew + Launch...
---

# Local AI Stack — Conventions d'appel (Host macOS personnel)

Stack AI/ML **personnelle** Michael Ahern, **installée nativement sur le disque** (Apple Silicon M3 Max via Homebrew + LaunchAgents + MLX). Couvre LiteLLM Proxy AI Gateway local (:8092), sidecar vector store pgvector (:8093), aictl + serveurs MLX, omlx FIM coder (:8000), conventions d'appel des modèles, et config Claude Code `settings.local.json`. Charger quand un projet mentionne "ai-servers", "aictl", "MLX", "LiteLLM Proxy host", "qwen3", "medgemma", "nemotron", "gemma4", "embedding local", "reranker local", "ANTHROPIC_BASE_URL", "apiKeyHelper", "omlx", "Continue VS Code", "PRO-G40", "local servers", "port 8092".

## Références

- [Périmètre — Deux stacks distincts, NE PAS confondre](references/perimetre-deux-stacks-distincts-ne-pas-confondre.md)
- [aictl — Référence rapide](references/aictl-reference-rapide.md)
- [Inventaire des serveurs](references/inventaire-des-serveurs.md)
- [PRO-G40 Disque externe](references/pro-g40-disque-externe.md)
- [omlx — FIM coder local (:8000)](references/omlx-fim-coder-local-8000.md)
- [Continue VS Code — stack 100% local](references/continue-vs-code-stack-100-local.md)
- [Toujours router via le LiteLLM Proxy (host perso uniquement)](references/toujours-router-via-le-litellm-proxy-host-perso-uniquement.md)
- [LiteLLM Gateway — état réel](references/litellm-gateway-etat-reel.md)
- [Modèles et aliases LiteLLM](references/modeles-et-aliases-litellm.md)
- [Pattern Python recommandé](references/pattern-python-recommande.md)
- [Claude Code (harness) — Routage via LiteLLM](references/claude-code-harness-routage-via-litellm.md)
- [Troubleshooting rapide](references/troubleshooting-rapide.md)
- [Caveats serveurs MLX — exceptions au routage LiteLLM](references/caveats-serveurs-mlx-exceptions-au-routage-litellm.md)
- [Pattern — Wrapper RAGAs natif pour MLX (sans langchain-openai)](references/pattern-wrapper-ragas-natif-pour-mlx-sans-langchain-openai.md)
- [Smoke tests `kg_pipeline.medical` (2026-05-11)](references/smoke-tests-kgpipelinemedical-2026-05-11.md)
- [Skills & rules associés](references/skills-rules-associes.md)
- [Anti-patterns à éviter](references/anti-patterns-a-eviter.md)
- [Ressources](references/ressources.md)
