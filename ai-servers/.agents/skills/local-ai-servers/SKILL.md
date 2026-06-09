---
name: local-ai-servers
description: |
  Manage the local AI/ML inference servers in this repository via `./aictl`.
  Use this project skill whenever Michael asks about ai-servers, aictl, local model
  server status, health checks, LaunchAgents, port conflicts, MLX servers,
  LiteLLM proxy, embeddings, reranker, GLiNER, Whisper STT, Kokoro TTS, oMLX,
  Ollama, or the PRO-G40 model-cache disk.
---

# Local AI Servers

## Scope

Use this skill only for the `/Users/michaelahern/ai-servers` checkout.
Start from the live repository state, not stale inventory notes.

Core files:

| Path             | Role                                                            |
| ---------------- | --------------------------------------------------------------- |
| `servers.yaml`   | Declarative server registry and source of truth                 |
| `launchers/*.sh` | One long-running service launcher per server                    |
| `logs/`          | Runtime logs, not source                                        |
| `aictl`          | Operational CLI for status, health, lifecycle, and LaunchAgents |

Load `references/server-registry.md` only when a task needs the server inventory,
ports, model details, venvs, or API compatibility.

## Commands

```bash
./aictl list
./aictl status
./aictl health
./aictl start <name>
./aictl stop <name>
./aictl restart <name>
./aictl logs <name>
./aictl install
```

Use `all` only when Michael explicitly asks for all services.

## Operating Pattern

1. Read `servers.yaml` before making claims about service definitions.
2. Check `./aictl status` before diagnosing runtime state.
3. Use `./aictl health` or a direct `curl` endpoint for readiness.
4. Inspect `logs/<server>.log` and `logs/<server>.error.log` for failures.
5. For LaunchAgent changes, use `./aictl install` after registry edits.
6. For LiteLLM changes, validate `litellm-proxy/config.yaml`, restart
   `litellm-proxy`, then check port `8092`.

## Guardrails

- Do not hard-code secrets into launchers or YAML.
- Preserve `127.0.0.1` binding unless Michael explicitly asks to expose a service.
- Do not treat logs, caches, `__pycache__`, or local backups as source.
- Heavy model services can depend on local cache state and memory pressure; verify
  before concluding a config change is bad.
- For `ollama` and `omlx`, remember lifecycle is Homebrew/launchd-owned even when
  `aictl` reports status and health.

## Expected Output

When answering Michael, include:

- concrete service names and ports
- the command run or the file inspected
- the observed status or error
- the next action, if any
