---
paths:
  - "openclaw/src/gateway/**/*.ts"
  - "openclaw/src/gateway/**/*.test.ts"
---

# Gateway, API & WebSocket

## Serveur

- HTTP/HTTPS natif Node.js (`node:http`/`node:https`) — pas Express/Fastify
- WebSocket via `ws` library
- Port defaut: 18789 (configurable)
- Bind: loopback (127.0.0.1), LAN (0.0.0.0), Tailscale, ou custom
- Boot: `src/gateway/boot.ts` → `src/gateway/server.impl.ts`

## Endpoints HTTP

| Endpoint                             | Methode | Usage                                                                |
| ------------------------------------ | ------- | -------------------------------------------------------------------- |
| `/health`, `/healthz`                | GET     | Liveness probe                                                       |
| `/ready`, `/readyz`                  | GET     | Readiness probe                                                      |
| `/v1/chat/completions`               | POST    | OpenAI-compatible (optionnel, config `gateway.http.chatCompletions`) |
| `/v1/responses`                      | POST    | OpenResponses (optionnel, SSE streaming)                             |
| `/tools/invoke`                      | POST    | Invocation d'outils (rate-limited)                                   |
| `/__openclaw__/ws`                   | WS      | Canvas WebSocket                                                     |
| `/__openclaw/control-ui-config.json` | GET     | Config bootstrap Control UI                                          |
| `/`                                  | GET     | SPA Control UI                                                       |

## WebSocket Protocol (68 methodes RPC)

Connexion sur `/` (meme port que HTTP). Frame structure:

- Request: `{ type: "request"|"stream", method, id, params }`
- Response: `{ type: "response"|"event"|"error", method?, id?, result?, error? }`

**Categories de methodes:**

- `config.*` — get/set/apply/patch/schema
- `chat.*` — send/history/inject/abort
- `agent.*` / `agents.*` — invoke/identity/wait/list/create/update/delete/files
- `sessions.*` — list/preview/patch/reset/delete/compact
- `node.*` — list/describe/rename/invoke/pair
- `cron.*` — list/status/add/update/remove/run
- `models.list`, `tools.catalog`, `skills.*`
- `health`, `usage.*`, `logs.tail`

**12 types d'events serveur → client:**
chat, agent, presence, tick, talk.mode, shutdown, health, heartbeat, cron,
node.pair._, device.pair._, exec.approval.\*, voicewake.changed, update.available

## Authentification

| Mode           | Methode                                                        |
| -------------- | -------------------------------------------------------------- |
| Token (defaut) | `Authorization: Bearer <token>` — 32 bytes random, timing-safe |
| Password       | Basic auth ou POST body                                        |
| Trusted Proxy  | User header extraction, allowlist                              |
| Tailscale      | Whois API, loopback forward                                    |
| Device         | Token device pour Control UI                                   |

Rate limiting: fixed-window, 20 failures/60s par IP.

## Fichiers cles

- `src/gateway/server-http.ts` — HTTP request handler principal
- `src/gateway/server.impl.ts` — Bootstrap serveur
- `src/gateway/server/ws-connection.ts` — Connexions WebSocket
- `src/gateway/server-methods-list.ts` — Liste des 68 methodes + 12 events
- `src/gateway/server-methods/` — Implementations (67 fichiers)
- `src/gateway/auth.ts` — Orchestration auth
- `src/gateway/auth-rate-limit.ts` — Rate limiter
- `src/gateway/openai-http.ts` — Endpoint OpenAI-compat
- `src/gateway/openresponses-http.ts` — Endpoint OpenResponses
- `src/gateway/control-ui.ts` — Serving Control UI
- `src/gateway/control-ui-csp.ts` — CSP headers

## Skills associes

Pour les operations gateway (demarrage, dev vs prod, troubleshooting): skill `intellisoins-openclaw:openclaw-gateway`
