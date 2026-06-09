# OpenClaw Codebase Modules

Expected source root: `~/openclaw/openclaw/`.

## Major Areas

| Module           | Responsibility                                                              |
| ---------------- | --------------------------------------------------------------------------- |
| `src/agents`     | Pi embedded runner, subagents, tools, skills, system prompts, models config |
| `src/infra`      | Network, env, TLS, binaries, rate limits, exec policies                     |
| `src/gateway`    | HTTP/WS server, protocol, auth, RPC, Control UI serving                     |
| `src/config`     | Config loading, schemas, sessions, types                                    |
| `src/commands`   | CLI commands                                                                |
| `src/channels`   | Multi-channel transports and routing                                        |
| `src/plugins`    | Loader, discovery, manifests, runtime                                       |
| `src/plugin-sdk` | Public plugin SDK                                                           |
| `src/security`   | Audit, dangerous tool flags, secret equality                                |
| `src/memory`     | Memory backends and schema                                                  |

## Root Files

| File                  | Role                  |
| --------------------- | --------------------- |
| `openclaw.mjs`        | CLI entry point       |
| `package.json`        | Monorepo scripts      |
| `pnpm-workspace.yaml` | Workspace definitions |
| `tsconfig.json`       | TypeScript config     |
| `vitest.config.ts`    | Test config           |
| `.oxlintrc.json`      | Oxlint config         |
| `tsdown.config.ts`    | Build config          |
