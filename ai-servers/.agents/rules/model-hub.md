---
paths:
  - "~/ai-servers/MODEL-CATALOG.yaml"
  - "~/ai-servers/litellm-proxy/**"
  - "~/.local/bin/claude-proxy"
  - "~/.local/bin/claude-omlx"
  - "~/.local/bin/models-catalog"
  - "~/.local/bin/cursor-omlx-config"
---

# Hub de modèles unifié (hybride)

Registre canonique : `~/ai-servers/MODEL-CATALOG.yaml`. Hub routable : **LiteLLM `:8092`**. Certaines voies restent **hors hub** par design.

## Matrice clients × backend

| Commande / client               | Backend                                                               | Centralisable ?       |
| ------------------------------- | --------------------------------------------------------------------- | --------------------- |
| `claude`                        | Vertex direct (`~/.claude/settings.json`, `CLAUDE_CODE_USE_VERTEX=1`) | Non (volontaire)      |
| `claude-local` / `claude-proxy` | LiteLLM `:8092` → oMLX / Together / Anthropic API                     | **Oui — cœur du hub** |
| `claude-omlx` / `cc-omlx`       | oMLX direct `:8211`                                                   | Fallback / debug perf |
| `agent` (Cursor CLI)            | Cursor cloud (`agentn.global.api5.cursor.sh`)                         | Non                   |
| Cursor Chat / Cmd+K             | LiteLLM OpenAI-compatible `:8092/v1`                                  | Partiellement         |

**Ne pas** mettre `ANTHROPIC_BASE_URL` dans `~/.claude/settings.json` global — court-circuite Vertex pour **toutes** les sessions `claude`.

## Alias LiteLLM normalisés

| Alias                   | Cible                               | Usage                                    |
| ----------------------- | ----------------------------------- | ---------------------------------------- |
| `code-local`            | `Qwen3-Coder-30B-A3B-Instruct-4bit` | Agent code local (défaut `claude-local`) |
| `general-local`         | `Qwen3.6-35B-A3B-4bit`              | Raisonnement / multimodal local          |
| `sonnet-together-coder` | `claude-together-qwen3-coder-480b`  | Code cloud cheap                         |
| `opus-anthropic`        | `anthropic-claude-opus`             | Cloud via clé Anthropic (hors Vertex)    |

Alias legacy conservés : `claude-local-qwen3-coder-30b`, `claude-local-qwen35-35b`, etc.

Override tiers Claude Code (hub) : `CLAUDE_OPUS`, `CLAUDE_SONNET`, `CLAUDE_HAIKU` — valeurs = alias LiteLLM.

**Note (2026-07-05)** : si `general-local` / `Qwen3.6-35B-A3B-4bit` est marqué unhealthy par le pre-call LiteLLM, utiliser `claude-omlx` avec `OMLX_OPUS=Qwen3.6-35B-A3B-4bit` en attendant le cooldown Redis (~60 s) ou un `aictl restart litellm-proxy`.

## Cursor CLI — limites

| Besoin          | Outil                                         |
| --------------- | --------------------------------------------- |
| Fable 5         | `agent --model claude-fable-5`                |
| Composer        | `agent --model composer-2.5`                  |
| Code local Qwen | `claude-local` ou `claude-omlx` (pas `agent`) |

Fable 5 = slug **Cursor uniquement** — pas sur Vertex, oMLX ni OpenRouter (extension future via `standby-models.yaml`).

## Ajouter un modèle

1. Entrée dans `MODEL-CATALOG.yaml`
2. Entrée dans `litellm-proxy/config.yaml` (`model_list` + alias si Claude Code)
3. Si oMLX : entrée dans `~/.omlx/model_settings.json`
4. Smoke : `aictl start litellm-proxy` puis `curl -H "Authorization: Bearer $MASTER" http://127.0.0.1:8092/v1/models`
5. Vérifier : `models-catalog`

## CLI utilitaires

| Script               | Rôle                                   |
| -------------------- | -------------------------------------- |
| `models-catalog`     | Vue unifiée YAML + probes LiteLLM/oMLX |
| `cursor-omlx-config` | Instructions Cursor Chat → LiteLLM     |
| `claude-proxy`       | Claude Code → hub                      |
| `claude-omlx`        | Claude Code → oMLX direct              |

## Smoke tests (checklist)

1. `aictl status litellm-proxy omlx` — les deux UP
2. `claude-proxy -p "dis bonjour" --model code-local` — réponse via LiteLLM
3. `claude -p "dis bonjour"` — Vertex non régressé
4. `claude-omlx -p "…"` — direct oMLX (fallback si LiteLLM down)
5. `models-catalog` — affiche hub + direct + cursor
6. Cursor Chat (manuel) — Override URL → `:8092/v1`, modèle `code-local`

## Cross-références

- `claude-code-litellm.md` — config LiteLLM DB-backed
- `omlx.md` — serveur oMLX local
- `apple_all/.cursor/rules/omlx.mdc` — section Hub LiteLLM
- `apple_all/.cursor/rules/inference-apple-silicon.mdc` — choix de stack serveur
