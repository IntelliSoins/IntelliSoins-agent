---
name: project-structure
description: Structure détaillée du projet openclaw intellisoins
---

# Structure du projet OpenClaw

## Racine du projet (openclaw/)

```
openclaw/                   # Racine projet
├── openclaw/               # Repo principal (monorepo pnpm)
├── pipeline/               # Scripts fine-tuning Python
│   ├── grpo/               # GRPO reinforcement learning
│   └── training-data/      # Datasets générés (9 variantes)
├── adapters/               # LoRA adapters (nemotron, qwen3, qwen35)
└── docs/                   # Plans et specs (plans/ et specs/ sous docs/superpowers/)
```

## Le Monorepo Principal (openclaw/openclaw/)

### Dossiers de base

- `src/` : Code serveur TypeScript ESM.
- `ui/` : Control UI (Lit 3 Web Components, Vite).
- `extensions/` : 137 plugins (channels, memory, auth, etc.).
- `skills/` : 59 skills bundled (format `SKILL.md`).
- `packages/` : 23 packages internes (clawdbot, moltbot, acp-core, agent-core, gateway-client, llm-core, terminal-core, net-policy, tool-call-repair, etc.).
- `apps/` : macOS/iOS/Android clients (y compris `macos-mlx-tts/` et `swabble/`).
- `test/` : Tests E2E.

### Structure détaillée de `src/`

Le répertoire `src/` contient les modules suivants :

- `cli/` : CLI Commander.js (program, commands, daemons).
- `gateway/` : Gateway HTTP/WS (méthodes RPC, protocoles).
- `agents/` : Agent runtime, embedded runner, providers, tools, skills, models.
- `channels/` : Transport multi-canal, routage des messages.
- `plugins/` : Plugin loader, Discovery, manifest registry, runtime.
- `plugin-sdk/` : SDK public pour les extensions.
- `security/` : Audit, validation de flags dangereux, secrets, gestion des permissions.
- `config/` : Configuration, schémas de validation Zod, sessions.
- `infra/` : Network, environnement, TLS, binaries, rate limit, exec policies.
- `acp/` : Support du protocole Agent Connection Protocol.
- `auto-reply/`, `chat/`, `talk/` : Logique de conversation et streaming de blocs de réponse.
- `context-engine/` : Gestion du contexte persistant et backends.
- `memory/` & `memory-host-sdk/` : Systèmes et backends de mémoire.
- `media/`, `media-generation/`, `media-understanding/` : Pipelines de compréhension et génération média.
- `video-generation/`, `image-generation/`, `tts/`, `realtime-transcription/` : Prise en charge multimodale avancée (audio/vidéo).
- `canvas-host/`, `tui/`, `wizard/` : Interfaces utilisateurs (Text-based, Wizard d'installation, Canvas A2UI).
- `cron/` : Tâches cron asynchrones.
- `flows/` : Workflows agentiques et flows.
