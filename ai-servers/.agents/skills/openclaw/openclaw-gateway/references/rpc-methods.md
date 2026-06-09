# OpenClaw Gateway RPC Methods And Events

## WebSocket Frames

Connection is on the gateway WebSocket endpoint.

Request:

```json
{ "type": "request", "method": "method.name", "id": "id", "params": {} }
```

Response:

```json
{ "type": "response", "id": "id", "result": {} }
```

## Method Categories

| Category     | Examples                                     |
| ------------ | -------------------------------------------- |
| `config.*`   | get, set, apply, patch, schema               |
| `chat.*`     | send, history, inject, abort                 |
| `agent.*`    | invoke, identity, wait                       |
| `agents.*`   | list, create, update, delete, files          |
| `sessions.*` | list, preview, patch, reset, delete, compact |
| `node.*`     | list, describe, rename, invoke, pair         |
| `cron.*`     | list, status, add, update, remove, run       |
| `models`     | list                                         |
| `tools`      | catalog                                      |
| `skills.*`   | list, get, update, delete                    |
| `usage.*`    | get, summary                                 |
| `logs`       | tail                                         |

## Auth Modes

| Mode          | Method                                |
| ------------- | ------------------------------------- |
| Token         | `Authorization: Bearer <token>`       |
| Password      | Basic auth or POST body               |
| Trusted proxy | User header extraction plus allowlist |
| Tailscale     | Whois API, loopback forward           |
| Device        | Control UI device token               |

## Key Files

| File                                  | Role                       |
| ------------------------------------- | -------------------------- |
| `src/gateway/server-http.ts`          | HTTP request handler       |
| `src/gateway/server.impl.ts`          | Server bootstrap           |
| `src/gateway/server/ws-connection.ts` | WebSocket connections      |
| `src/gateway/server-methods-list.ts`  | Method and event list      |
| `src/gateway/server-methods/`         | Method implementations     |
| `src/gateway/auth.ts`                 | Auth orchestration         |
| `src/gateway/auth-rate-limit.ts`      | Auth rate limiter          |
| `src/gateway/openai-http.ts`          | OpenAI-compatible endpoint |
| `src/gateway/openresponses-http.ts`   | OpenResponses endpoint     |
| `src/gateway/control-ui.ts`           | Control UI serving         |

## HTTP Endpoints

| Endpoint               | Method | Purpose           |
| ---------------------- | ------ | ----------------- |
| `/health`, `/healthz`  | GET    | Liveness          |
| `/ready`, `/readyz`    | GET    | Readiness         |
| `/v1/chat/completions` | POST   | OpenAI-compatible |
| `/v1/responses`        | POST   | OpenResponses     |
| `/tools/invoke`        | POST   | Tool invocation   |
| `/`                    | GET    | Control UI SPA    |
