---
name: openclaw-dev
description: >
  Use this project skill when Michael asks to build OpenClaw, run tests, fix
  build errors, run pnpm install, lint, format, merge upstream, or troubleshoot
  OpenClaw/OpenIntellisoins development failures.
---

# OpenClaw Dev Workflow

## Scope

Use this skill for the OpenClaw/OpenIntellisoins checkout at
`~/openclaw/openclaw/`. The global binary is expected to be `openclaw` via
`npm link`, and runtime config is `~/.openclaw/openclaw.json`.

Load `references/codebase-modules.md` only when the user asks for the codebase
map, module ownership, or file locations.

## Commands

```bash
pnpm install
pnpm build
pnpm test
pnpm check
pnpm format:fix
pnpm dev
pnpm ui:build
pnpm ui:dev
```

## Workflow

1. Start in `~/openclaw/openclaw/`.
2. Read the failing command output before changing anything.
3. Run the narrow command first (`pnpm ui:build`, targeted Vitest, or package
   build) before full-suite validation.
4. For upstream merges, preserve local French/i18n work and re-run install plus
   build checks.

## Common Failure

If `pnpm build` fails around `write-cli-startup-metadata`, verify whether this is
the known upstream metadata generation issue before changing unrelated files.

For i18n regressions, check:

- `ui/src/i18n/locales/fr.ts`
- `ui/src/ui/views/*.ts`
- `t("section.key")` calls replacing hard-coded UI strings
