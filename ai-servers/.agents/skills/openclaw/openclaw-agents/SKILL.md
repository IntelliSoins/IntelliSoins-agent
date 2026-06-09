---
name: openclaw-agents
description: >
  Use this project skill when Michael asks to configure OpenClaw providers,
  add a local LLM, switch model, configure Qwen3.5, inspect OpenClaw tools,
  subagents, system prompts, Pi SDK agent runtime, or model provider config.
---

# OpenClaw Agents And Providers

## Scope

Use this skill for OpenClaw/OpenIntellisoins agent configuration from this
machine. The main OpenClaw repo is expected at `~/openclaw/openclaw/`, with
runtime config at `~/.openclaw/openclaw.json`.

Load `references/providers-catalog.md` only when the user asks about provider
types, discovery, failover, or the provider registry files.

## Current Local Provider

Primary local provider:

```json
{
  "providers": {
    "mlx-qwen35": {
      "type": "openai-compatible",
      "baseUrl": "http://localhost:8087/v1",
      "model": "qwen3.5-35b-a3b",
      "contextWindow": 262144,
      "reasoning": true
    }
  },
  "agents": {
    "default": { "provider": "mlx-qwen35" }
  }
}
```

Check the local model server before debugging OpenClaw agent behavior:

```bash
curl http://localhost:8087/v1/models
```

## Key Files

| File                                   | Role                    |
| -------------------------------------- | ----------------------- |
| `src/agents/pi-embedded-runner/run.ts` | Agent runtime lifecycle |
| `src/agents/tool-catalog.ts`           | Tool catalog            |
| `src/agents/tool-policy.ts`            | Tool allowlists         |
| `src/agents/subagent-registry.ts`      | Subagent registry       |
| `src/agents/subagent-spawn.ts`         | Subagent spawning       |
| `src/agents/system-prompt.ts`          | Dynamic system prompt   |

## Troubleshooting

For Qwen3.5 failures:

1. Check `curl http://localhost:8087/v1/models`.
2. If the call times out, the model may still be loading.
3. If OpenClaw hangs, inspect gateway logs and active connections to port `8087`.
4. If tool calling fails, verify provider `reasoning: true` and OpenAI-compatible
   tool call support.
