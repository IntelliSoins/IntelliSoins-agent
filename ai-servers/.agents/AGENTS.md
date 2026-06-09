<goal>
1.Avoir une configuration pour mon IA sur mon Macbook pro 128go de mémoire unifié, avec LiteLLM comme ai gateway proxy, qui gate vers des llm, reranker, realtime voice, sst, tts, et qui eux qui infère les modèles via omlx, vmlx, vllm-mlx, et d'autres au fil du temps.
2.Le but est d'avoir une configuration qui optimise l'utilisation d'agents ia open source optimisé pour de long contexte, de type agentique, pour faire des <task></task> de gestion d'agenda, courriels, finances et pour ce faire, doivent être optimisé pour l'utilisation d'outils, recherche web, et la sécurité.
3.Utiliser openclaw comme projet de base pour le transformer en interface agentic optimisé Apple Silicon M1,M2,M3,M4,M5, agentic longue task flow
</goal>

<url>
Consulter obligatoirement les https://github.com/waybarrios/vllm-mlx, https://github.com/jundot/omlx,https://github.com/jjang-ai/vmlx, et d'autres
</url>

# Repository Guidelines

## Project Structure & Module Organization

This repository manages local AI services on macOS. `aictl` is the main control script, and `servers.yaml` is the source of truth for server definitions, ports, LaunchAgent settings, and health endpoints.

- `launchers/`: executable shell launchers for each service.
- `litellm-proxy/`: LiteLLM gateway configuration and activation notes.
- `templates/`: model prompt/chat templates.
- `logs/`: runtime logs; do not treat logs as source.
- `turboquant_patch.py`: Python patch used by selected MLX/TurboQuant servers.

There is no dedicated test directory. Validation is operational through `aictl` and service health endpoints.

## Build, Test, and Development Commands

- `./aictl list`: show registered services, categories, ports, and disk requirements.
- `./aictl status`: inspect process, port, memory, and uptime state.
- `./aictl health`: run HTTP health checks for configured services.
- `./aictl start <name>` / `./aictl stop <name>` / `./aictl restart <name>`: control one service; use `all` only when intended.
- `./aictl logs <name>`: tail service logs.
- `./aictl install`: regenerate and load LaunchAgents after registry changes.

For LiteLLM changes, validate `litellm-proxy/config.yaml`, restart with `./aictl restart litellm-proxy`, and check port `8092`.

## Coding Style & Naming Conventions

Shell scripts should use Bash, keep environment setup near the top, and end with `exec ...` for the long-running process. Use lowercase kebab-case server IDs, such as `qwen35-35b` or `litellm-proxy`, and align launcher filenames.

YAML uses two-space indentation. New `servers.yaml` entries need explicit `category`, `port`, `host`, `launcher`, `log_stdout`, `log_stderr`, `health_endpoint`, and `throttle` fields. Python follows PEP 8 with four-space indentation.

## Testing Guidelines

Before changing launch behavior, run `./aictl list` to confirm the registry parses and `./aictl status` to identify affected services. After edits, run `./aictl health`; for one service, restart it and verify its endpoint, such as `curl http://127.0.0.1:8084/health`.

Avoid committing generated files from `logs/`, `__pycache__/`, or local backup files.

## Commit & Pull Request Guidelines

This checkout has no local `.git` history, so no existing convention can be inferred. Use concise imperative commits such as `Update LiteLLM aliases` or `Add Qwen vision launcher`.

Pull requests should describe service impact, changed ports or LaunchAgent behavior, required secrets or external paths, and validation output from `./aictl status` and `./aictl health`.

## Security & Configuration Tips

Do not hard-code API keys in launchers or YAML. Keep cloud keys in `litellm-proxy/.env` or macOS Keychain as the existing LiteLLM launcher does. Preserve `127.0.0.1` binding unless a service is intentionally exposed.

<openclaw>
# OpenIntellisoins — Instructions Projet (fork personnel d'OpenClaw)

## Usage local (Michael Ahern)

- Banc de test pour modeles fine-tunes dans un agentic flow local
- LLM locaux seulement (Qwen3.5-35B-A3B sur port 8087) — pas de cloud/API Anthropic
- Gateway: `localhost:18789` (bind loopback, token auth)
- Config: `~/.openclaw/openclaw.json`
  - **Canal WhatsApp Web (Baileys)** : Activé & Configuré (dmPolicy: pairing, groupPolicy: allowlist, timings watchdog/keepalive optimisés, approvals via +18194421082).
  - **Rapport WhatsApp** : [Rapport de configuration WhatsApp](file:///Users/michaelahern/.gemini/antigravity-cli/brain/cb0546ae-c54d-41a7-bae4-6401a0ed164f/whatsapp_setup_report.md)
- Skills manages: `~/.openclaw/skills/` (196 charges depuis Codex)

## Conventions upstream

Le repo contient un `openclaw/AGENTS.md` (symlinke comme `AGENTS.md`) avec les guidelines
maintainer upstream (27KB). Consulter ce fichier pour les conventions de code, PR workflow,
release process, et security model. Points cles:

- Fichiers repo-root relative dans les references (pas de chemins absolus)
- Tests colocates `*.test.ts` avec V8 coverage 70%
- Oxlint + Oxfmt pour lint/format (`pnpm check`)
- ESM strict, TypeScript strict, pas de `any` sans justification
- Fichiers sous ~700 LOC guideline

## Build & Test

```
pnpm install          # Installer les dependances
pnpm build            # TypeScript → ESM dist
pnpm test             # Vitest suite
pnpm check            # Oxlint + Oxfmt
pnpm format:fix       # Oxfmt --write
pnpm dev              # Dev mode avec reload
pnpm gateway:dev      # Gateway server seulement
pnpm ui:build         # Build Control UI → dist/control-ui/
pnpm openclaw ...     # CLI execution
```

## Pipeline fine-tuning (Python)

```
cd pipeline/
python extract_claude_sessions.py     # Etape 1: extraire sessions
python convert_anthropic_to_openai.py # Etape 2: format Anthropic → OpenAI
python enrich_openclaw_tools.py       # Etape 3: enrichir avec tools OpenClaw
python build_training_dataset.py      # Etape 4: dataset final + LoRA config
python -m grpo.run --config grpo/config.yaml  # GRPO (RL sur LoRA)
pytest test_*.py -v                   # Tests pipeline
```

## Structure du projet

```
openclaw/                   # Racine projet
├── openclaw/               # Repo principal (monorepo pnpm)
│   ├── src/                # Code serveur TypeScript ESM
│   │   ├── cli/            # CLI (Commander.js)
│   │   ├── gateway/        # Gateway HTTP/WS (68 methodes RPC)
│   │   ├── agents/         # Agent runtime (Pi SDK), providers, tools
│   │   ├── channels/       # Transport multi-canal
│   │   ├── plugins/        # Plugin loader et runtime
│   │   ├── plugin-sdk/     # SDK public pour extensions
│   │   ├── security/       # Audit, permissions, secrets
│   │   ├── config/         # Config Zod schemas
│   │   ├── infra/          # Network, env, TLS, binaries
│   │   ├── acp/            # Agent Connection Protocol
│   │   ├── auto-reply/     # Reponses automatiques / conversation
│   │   ├── context-engine/ # Persistance de contexte
│   │   ├── memory/         # Backends de memoire
│   │   ├── media/          # Pipelines multimedia (generation/understanding)
│   │   ├── tts/            # Text-to-speech
│   │   ├── realtime-transcription/ # Transcription en temps reel
│   │   ├── tui/            # Interface utilisateur textuelle (TUI)
│   │   ├── canvas-host/    # Service d'UI Canvas (A2UI)
│   │   └── cron/           # Planification de taches
│   ├── ui/                 # Control UI (Lit 3 Web Components, Vite)
│   ├── extensions/         # 137 plugins (channels, memory, auth, etc.)
│   ├── skills/             # 59 skills bundled (SKILL.md format)
│   ├── packages/           # 23 packages (shims + core modules, clawdbot, moltbot, etc.)
│   ├── apps/               # iOS, Android, macOS (y compris macos-mlx-tts, swabble)
│   └── test/               # E2E tests
├── pipeline/               # Scripts fine-tuning Python (grpo/, training-data/)
├── adapters/               # LoRA adapters (nemotron, qwen3, qwen35)
└── docs/                   # Plans et specs (sous docs/superpowers/)
```

## Rules par domaine

Les fichiers `.Codex/rules/*.md` contiennent les details par domaine:

- `architecture.md` — stack, monorepo, patterns
- `gateway-api.md` — endpoints, WebSocket, auth (charge avec `src/gateway/`)
- `ai-agents.md` — providers, agent runtime, tools (charge avec `src/agents/`)
- `frontend-ui.md` — Lit components, i18n, state (charge avec `ui/`)
- `docker-infra.md` — Dockerfiles, compose, deploy (charge avec `Dockerfile*`)
- `security.md` — permissions, sandbox, secrets (charge avec `src/security/`)
- `pipeline-finetuning.md` — fine-tuning, GRPO, adapters (charge avec `pipeline/`)
