---
name: openclaw-frontend
description: >
  Use this project skill when Michael asks to build the OpenClaw UI, translate
  OpenClaw, add i18n keys, fix the Control UI, work with Lit components, change
  the dashboard header, or modify the `ui/` web interface.
---

# OpenClaw Frontend

## Scope

Use this skill for the Control UI in `~/openclaw/openclaw/ui/`.
Load `references/components-map.md` only when component/controller mapping is
needed.

## Stack

- Lit 3 Web Components
- Vite build
- Reactive controllers
- i18n locales: `en`, `fr`, `zh-CN`, `zh-TW`, `pt-BR`, `de`, `es`
- DOMPurify plus marked for Markdown rendering

## Commands

```bash
pnpm ui:build
pnpm ui:dev
pnpm ui:preview
```

## Entry Point

```text
ui/index.html
  -> ui/src/main.ts
  -> ui/src/ui/app.ts
  -> ui/src/ui/app-render.ts
```

## i18n Pattern

Add French strings in `ui/src/i18n/locales/fr.ts`, then use `t("section.key")`
from a Lit `I18nController`.

```typescript
import { I18nController } from "../../i18n/lib/lit-controller.js";

export class MyComponent extends LitElement {
  private i18n = new I18nController(this);

  render() {
    const t = this.i18n.t;
    return html`<h1>${t("section.title")}</h1>`;
  }
}
```

## Guardrails

- Do not introduce React/Vue patterns into the Lit codebase.
- Keep user-visible strings in locale files where the surrounding code uses i18n.
- Check `pnpm ui:build` after UI changes.
- Preserve the OpenIntellisoins rebrand where already present.
