---
paths:
  - "openclaw/src/security/**/*.ts"
  - "openclaw/src/infra/host-env-security*"
  - "openclaw/src/infra/exec-safe-bin*"
  - "openclaw/src/infra/pairing-token*"
  - "openclaw/src/infra/fixed-window*"
  - "openclaw/SECURITY.md"
---

# Securite & Permissions

## Trust model

Personal assistant (operateur unique, pas multi-tenant).
Les appelants authentifies du gateway sont traites comme operateurs de confiance.
Plugins/extensions charges in-process = meme niveau de confiance que le code local.

## Authentification gateway

| Mode          | Implementation                                              |
| ------------- | ----------------------------------------------------------- |
| Token         | 32 bytes random (base64url), `timingSafeEqual()` via SHA256 |
| Password      | Basic auth ou POST, meme protection timing-safe             |
| Trusted Proxy | Header extraction + allowlist                               |
| Tailscale     | Whois API, loopback forward                                 |
| Device        | Token device pour Control UI                                |

Rate limiting: `src/infra/fixed-window-rate-limit.ts` — 20 failures/60s par IP.
Tokens: `src/infra/pairing-token.ts` — generation crypto-grade.

## Permissions tools

- **Gateway HTTP deny list** (`src/security/dangerous-tools.ts`):
  sessions_spawn, sessions_send (RCE), cron/gateway (reconfig), whatsapp_login (hang)
- **ACP require approval**: exec, spawn, shell, fs_write, fs_delete, fs_move, apply_patch
- **DM Policy** (par canal): pairing (defaut), allowlist, open, disabled
- **File system**: `tools.fs.workspaceOnly: true` restreint read/write au workspace

## Sandbox env sanitization

`src/infra/host-env-security-policy.json`:

- **Bloques**: NODE*OPTIONS, NODE_PATH, DYLD*\_, LD\_\_, BASH_ENV, IFS
- **Bloques si overrides**: HOME, GIT*SSH_COMMAND, NPM_CONFIG*\*
- **Safe**: TERM, LANG, LC\_\*, COLORTERM, NO_COLOR

## Secrets management

```typescript
type SecretInput = string | SecretRef;
type SecretRef = { source: "env" | "file" | "exec"; provider; id };
```

Env template: `${ENV_VAR_NAME}` → SecretRef automatique.
Redaction pour audit: `src/config/redact-snapshot.secret-ref.ts`.

## CSP (Control UI)

```
default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'
script-src 'self'; style-src 'self' 'unsafe-inline' fonts.googleapis.com
img-src 'self' data: https:; connect-src 'self' ws: wss:
```

Headers: X-Content-Type-Options: nosniff, Referrer-Policy: no-referrer.

## Pre-commit (.pre-commit-config.yaml)

1. `detect-secrets` v1.5 — detection de secrets (baseline: `.secrets.baseline`)
2. `detect-private-key` — cles privees
3. `shellcheck` v0.11 — lint shell (severity: error)
4. `zizmor` v1.22 — audit GitHub Actions (severity: medium)
5. `pnpm audit --prod --audit-level=high`
6. Oxlint, Oxfmt, ruff (Python), swiftlint, swiftformat

## Security audit CLI

`openclaw security audit` (modes: --deep, --fix):

- Dangerous flags, plugin trust, sandbox config
- Secrets in config, file permissions (POSIX + Windows)
- Channel policies, tool policy parity
- Model tier (prompt injection risk)

## Fichiers cles

- `src/security/audit.ts` — commande audit
- `src/security/dangerous-tools.ts` — deny list tools
- `src/security/dangerous-config-flags.ts` — flags break-glass
- `src/security/secret-equal.ts` — comparaison timing-safe
- `src/gateway/auth.ts` — orchestration auth
- `src/infra/host-env-security-policy.json` — politique env vars
- `src/infra/exec-safe-bin-policy.ts` — safe binary profiles
