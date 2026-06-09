---
name: openclaw-gateway
description: >
  Use this project skill when Michael asks to start the OpenClaw gateway,
  configure OpenClaw, fix gateway hangs, compare gateway dev vs prod, edit
  openclaw.json, troubleshoot WebSocket connections, auth, or gateway health.
---

# OpenClaw Gateway

## Scope

Use this skill for OpenClaw gateway operations on this machine.
Load `references/rpc-methods.md` only when RPC methods, events, auth modes, or
endpoint details are needed.

## Dev Vs Prod

| Area        | `pnpm gateway:dev`              | `openclaw gateway`          |
| ----------- | ------------------------------- | --------------------------- |
| Config      | `~/.openclaw-dev/openclaw.json` | `~/.openclaw/openclaw.json` |
| Port        | 19001                           | 18789                       |
| Token       | auto-generated                  | stable token in config      |
| Channels    | often skipped                   | active                      |
| Local model | usually not local by default    | `mlx-qwen35` config         |

Use `openclaw gateway` for local Qwen3.5 testing.

## Commands

```bash
openclaw gateway
openclaw gateway --allow-unconfigured
pnpm gateway:dev
curl -s http://127.0.0.1:18789/health
```

Control UI should be reachable at:

```text
http://127.0.0.1:18789
```

## Config

Primary config:

```json
{
  "gateway": {
    "port": 18789,
    "bind": "127.0.0.1",
    "auth": { "token": "<64-chars-random>" }
  },
  "agents": {
    "default": { "provider": "mlx-qwen35" }
  }
}
```

## Troubleshooting

Gateway hang:

1. `lsof -i :18789`
2. `lsof -i :8087`
3. If connections to Qwen3.5 are stuck, kill stale OpenClaw processes.
4. Restart with `openclaw gateway`.

Port already used:

```bash
lsof -i :18789
```

Token auth:

- token is in `~/.openclaw/openclaw.json`
- Control UI can use device pairing or the token directly
