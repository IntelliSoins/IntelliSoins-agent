---
paths:
  - "openclaw/src/agents/**/*.ts"
  - "openclaw/src/providers/**/*.ts"
  - "openclaw/src/context-engine/**/*.ts"
  - "openclaw/src/memory/**/*.ts"
---

# AI, LLM Providers & Agents

## Providers LLM (20+)

Abstraction via pi-ai. Providers configures dans `src/agents/models-config.providers.ts`:

- **Cloud**: Anthropic, OpenAI, Google Gemini, OpenRouter, Together, NVIDIA, Bedrock
- **Self-hosted**: Ollama (auto-discovery), Huggingface, custom OpenAI-compat
- **Regional**: Qwen (Alibaba), Kimi (Moonshot), BytePlus/Doubao, Qianfan (Baidu), Xiaomi
- **Auth OAuth**: GitHub Copilot, Gemini CLI, Qwen Portal, Minimax Portal

Config provider: `models-config.providers.ts` (registre), `models-config.providers.static.ts` (statique),
`models-config.providers.discovery.ts` (auto-discovery Ollama/HF/Kilocode).

## Agent Runtime

**Embedded runner** (defaut): `src/agents/pi-embedded-runner/run.ts`

- Pi coding agent SDK (`@mariozechner/pi-coding-agent`)
- Lifecycle: bootstrap → model resolution → tool prep → API call → result → failover

**Subagent system**:

- `subagent-registry.ts` — registre central
- `subagent-spawn.ts` — spawn et lifecycle
- `subagent-announce.ts` — notification parent

## Tool Catalog

40+ core tools organises en profiles dans `src/agents/tool-catalog.ts`:

- **Files**: read, write, edit, apply_patch
- **Runtime**: exec, process
- **Web**: web_search, web_fetch, browser
- **Memory**: memory_search, memory_get
- **Sessions**: sessions_access, sessions_history
- **Messaging**: send, react, edit (par canal)
- **Agents**: agent_step, subagents

Profiles: minimal, coding, messaging, full.
Policies: `tool-policy.ts` (allowlists par agent/sender).

## System Prompt

Construction dynamique dans `src/agents/system-prompt.ts`:

1. **Identity**: agent ID, workspace, runtime (host, OS, arch, node)
2. **Model aliases**: modeles disponibles + fallback order
3. **Tools**: noms + descriptions des tools actifs
4. **Skills**: SKILL.md guidance
5. **Memory**: instructions memory_search/memory_get
6. **Workspace**: senders autorises, actions par canal
7. **Runtime**: thinking levels, timezone

Modes: `full` (agent principal), `minimal` (subagents), `none` (identity seule).

## Streaming

- **Slack**: ChatStreamer natif (`src/slack/streaming.ts`)
- **Discord/Telegram**: message edit / reaction updates
- **SSE**: `src/signal/sse-reconnect.ts`
- **TUI**: `src/tui/tui-stream-assembler.ts`
- **Block streaming**: `src/auto-reply/reply/block-streaming.ts`

## Context & Memory

- `src/context-engine/` — backends de persistance (init, registry, types)
- `src/memory/memory-schema.ts` — schema memoire
- `src/agents/tools/memory-tool.ts` — tools memory_search/memory_get
- Compaction: `src/agents/pi-embedded-runner/compact.ts`

## Fichiers cles

- `src/agents/pi-embedded-runner/run.ts` — orchestration agent principale
- `src/agents/pi-embedded-runner/system-prompt.ts` — system prompt builder
- `src/agents/models-config.providers.ts` — registre providers
- `src/agents/tool-catalog.ts` — catalogue tools + profiles
- `src/agents/tool-policy.ts` — permissions tools
- `src/agents/subagent-registry.ts` — lifecycle subagents
- `src/agents/failover-error.ts` — classification failover
- `src/agents/sanitize-for-prompt.ts` — protection prompt injection
- `src/config/zod-schema.agents.ts` — validation Zod

## Skills associes

Pour la config providers locaux et troubleshooting: skill `intellisoins-openclaw:openclaw-agents`
