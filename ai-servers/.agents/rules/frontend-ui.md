---
paths:
  - "openclaw/ui/**/*.ts"
  - "openclaw/ui/**/*.css"
  - "openclaw/ui/**/*.html"
---

# Frontend Control UI

## Stack

- **Framework**: Lit 3.3 (Web Components, pas React/Vue)
- **Build**: Vite 7.3 → `dist/control-ui/`
- **State**: @state decorators + @lit-labs/signals + Reactive Controllers
- **i18n**: 7 langues (en default + fr, zh-CN, zh-TW, pt-BR, de, es lazy-loaded)
- **Styling**: CSS modules avec variables (dark/light theme)
- **Securite**: DOMPurify pour rendu HTML, marked pour Markdown

## Entry point

```
ui/index.html → <openclaw-app>
  → ui/src/main.ts (imports styles + app)
    → ui/src/ui/app.ts (LitElement, composant racine)
      → ui/src/ui/app-render.ts (logique de rendu)
```

## Vues principales (ui/src/ui/views/)

| Vue       | Fichier                     | Description                                    |
| --------- | --------------------------- | ---------------------------------------------- |
| Overview  | `overview.ts`               | Tableau de bord                                |
| Chat      | `chat.ts`                   | Interface chat (messages, streaming)           |
| Agents    | `agents.ts` + panels        | Config agents, outils, skills, status          |
| Channels  | `channels.ts` + per-channel | Config canaux (discord, slack, telegram, etc.) |
| Config    | `config.ts` + form          | Configuration systeme (formulaire dynamique)   |
| Sessions  | `sessions.ts`               | Gestion sessions                               |
| Skills    | `skills.ts`                 | Catalogue skills                               |
| Cron      | `cron.ts`                   | Taches programmees                             |
| Nodes     | `nodes.ts`                  | Noeuds distribues                              |
| Usage     | `usage.ts`                  | Metriques et analytics                         |
| Logs      | `logs.ts`                   | Logs systeme                                   |
| Instances | `instances.ts`              | Instances en cours                             |
| Debug     | `debug.ts`                  | Outils debug                                   |

## Communication serveur

`ui/src/ui/gateway.ts` — classe `GatewayBrowserClient`:

- WebSocket bidirectionnel vers le gateway
- Auth via device token
- Controllers dans `ui/src/ui/controllers/` (chat, agents, channels, config, cron, sessions, devices, etc.)

## i18n

- Manager: `ui/src/i18n/lib/translate.ts` (I18nManager)
- Locales: `ui/src/i18n/locales/{en,fr,zh-CN,zh-TW,pt-BR,de,es}.ts`
- Integration Lit: `ui/src/i18n/lib/lit-controller.ts` (ReactiveController)
- Persistance: `localStorage` key `openclaw.i18n.locale`
- API: `t("key.subkey", { param: "value" })`

## Commandes

```
pnpm ui:build    # Build production → dist/control-ui/
pnpm ui:dev      # Dev server Vite port 5173
pnpm ui:preview  # Preview build
```

## Apps natives (apps/)

- `apps/ios/` — iOS (SwiftUI)
- `apps/android/` — Android (Kotlin)
- `apps/macos/` — macOS (SwiftUI)
- `apps/shared/` — Code partage

## Skills associes

Pour les workflows i18n FR et patterns Lit: skill `intellisoins-openclaw:openclaw-frontend`
