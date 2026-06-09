# Architecture OpenClaw

## Stack technique

- **Langage**: TypeScript ESM (ES2023), Node.js 22+
- **Package manager**: pnpm (monorepo workspaces)
- **Build**: tsdown (bundler) → `dist/`
- **Test**: Vitest 4.x, V8 coverage 70%
- **Lint/Format**: Oxlint + Oxfmt (`pnpm check`)
- **UI**: Lit 3.3 Web Components, Vite 7.3
- **Agent SDK**: `@mariozechner/pi-*` (pi-agent-core, pi-ai, pi-coding-agent, pi-tui)
- **CLI**: Commander.js
- **Server**: HTTP/WS natif Node.js (pas Express/Fastify)

## Pattern architectural

Gateway monolithique hub-and-spoke avec channels pluggables:

1. **Gateway** — serveur central qui route messages entre channels, execute agents, gere auth
2. **Channels** — adapteurs par plateforme (Telegram, Discord, Slack, Signal, iMessage, web, etc.)
3. **Agent Runtime** — execute agents via Pi SDK, fournit tools, retourne reponses structurees
4. **Plugin Ecosystem** — packages externes dans `extensions/`, charges au runtime

## Monorepo (pnpm-workspace.yaml)

```
Workspaces:
  - root (openclaw CLI + gateway + agents)
  - ui/ (Control UI)
  - packages/* (clawdbot, moltbot — compat shims)
  - extensions/* (40+ plugins)
```

## Entry points

```
openclaw.mjs              # CLI entry (ESM wrapper, Node version check)
  → src/entry.ts          # Argument parsing, respawning, init
    → src/index.ts        # CLI program definition
      → src/cli/run-main.ts  # Dispatch vers subcommands
        → src/gateway/boot.ts  # Gateway bootstrap
```

## Modules principaux dans src/

| Module            | Responsabilite                                                             |
| ----------------- | -------------------------------------------------------------------------- |
| `cli/`            | CLI (program, gateway-cli, daemon-cli, node-cli, browser-cli, models-cli)  |
| `gateway/`        | Server HTTP/WS, protocol, auth, methods (68 RPC), control UI               |
| `agents/`         | Pi embedded runner, subagents, tools, skills, system prompt, models config |
| `channels/`       | Transport multi-canal, registry, routing                                   |
| `plugins/`        | Loader, discovery, manifest registry, runtime                              |
| `plugin-sdk/`     | API publique (48 entry points par channel)                                 |
| `config/`         | Config loading, Zod schemas, sessions, types                               |
| `security/`       | Audit, dangerous tools/flags, secret equality                              |
| `infra/`          | Network, env, TLS, binaries, rate limit, exec policies                     |
| `auto-reply/`     | Reply generation, templating, block streaming                              |
| `memory/`         | Memory backends, schema                                                    |
| `context-engine/` | Context persistence, backends                                              |
| `media/`          | Media pipeline, understanding                                              |
| `tts/`            | Text-to-speech                                                             |
| `browser/`        | Browser automation routes                                                  |
| `canvas-host/`    | A2UI bundle hosting                                                        |

## Dependances runtime cles

- `@agentclientprotocol/sdk` — Agent Client Protocol
- `grammy` (Telegram), `@slack/bolt`, `discord-api-types`, `@line/bot-sdk`
- `express` ^5.2 (Control UI serving), `ws` ^8.19 (WebSocket)
- `sqlite-vec` (memory backends)
- `zod`, `yaml`, `chalk`, `commander`, `jiti`

## Skills associes

Pour les guides proceduraux (build, troubleshooting, workflow): skill `intellisoins-openclaw:openclaw-dev`
