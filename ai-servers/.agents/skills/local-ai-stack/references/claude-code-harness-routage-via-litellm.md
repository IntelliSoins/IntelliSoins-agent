## Claude Code (harness) — Routage via LiteLLM

Deux patterns distincts selon le modèle visé. Ne pas mélanger.

### Pattern A — Modèles non-Anthropic (master key)

Sert à utiliser MLX local, Together AI, Ollama, OpenAI cloud, etc. depuis Claude Code via LiteLLM. Auth = master key Keychain.

`<projet>/.claude/settings.local.json` :

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://localhost:8092",
    "CLAUDE_CODE_API_KEY_HELPER_TTL_MS": "3600000"
  },
  "apiKeyHelper": "/Users/michaelahern/ai-servers/.claude/get-litellm-key.sh",
  "model": "claude-together-qwen3-coder-480b",
  "enabledPlugins": {
    "intellisoins-litellm@intellisoins-plugins": true
  }
}
```

Helper `get-litellm-key.sh` (chmod +x) :

```bash
#!/bin/bash
set -euo pipefail
security find-generic-password -a "$USER" -s litellm-master-key -w
```

Champs clés :

- `ANTHROPIC_BASE_URL` : redirige Claude Code vers le proxy local. LiteLLM expose une API compatible Anthropic.
- `apiKeyHelper` : script qui retourne la master key. JAMAIS de clé en clair dans `settings.local.json`. TTL `3600000` = 1 h.
- `model` : nom de modèle dans `~/ai-servers/litellm-proxy/config.yaml`.

Référence projet de travail : `~/ai-servers/.claude/settings.local.json`.

### Pattern B — Subscription Claude Max (OAuth forwarding)

Sert à utiliser sa subscription **Claude Max** depuis Claude Code MAIS en passant par LiteLLM (tracking, budgets, guardrails). Auth = double : virtual key LiteLLM + OAuth token Max forwardé. Ce pattern est utile quand le login Max direct cassé OU quand on veut tracker l'usage Max par utilisateur/team.

**Étape 1 — Modifier le proxy** `~/ai-servers/litellm-proxy/config.yaml` :

```yaml
model_list:
  - model_name: anthropic-claude
    litellm_params:
      model: anthropic/claude-sonnet-4-20250514
  - model_name: claude-3-5-haiku-20241022
    litellm_params:
      model: anthropic/claude-3-5-haiku-20241022

general_settings:
  forward_client_headers_to_llm_api: true # CRITIQUE — forward OAuth Max → Anthropic

litellm_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
```

Sans `forward_client_headers_to_llm_api: true`, le OAuth token est dropped → 401 Anthropic.

Pour granularité par modèle (recommandé en multi-tenant) :

```yaml
litellm_settings:
  model_group_settings:
    forward_client_headers_to_llm_api:
      - anthropic-claude
      - claude-3-5-haiku-20241022
```

**Étape 2 — Créer une virtual key LiteLLM** (Admin UI `http://127.0.0.1:8092/ui` → Virtual Keys → Create) ou via API :

```bash
MASTER=$(security find-generic-password -a "$USER" -s litellm-master-key -w)
curl -X POST "http://127.0.0.1:8092/key/generate" \
  -H "Authorization: Bearer $MASTER" \
  -H "Content-Type: application/json" \
  -d '{"key_alias":"claude-code-max","models":["anthropic-claude","claude-3-5-haiku-20241022"],"max_budget":100.00,"budget_duration":"monthly"}'
```

Stocker la clé `sk-...` retournée dans Keychain (jamais en clair dans `settings.local.json`) :

```bash
security add-generic-password -a "$USER" -s litellm-claude-code-vkey -w 'sk-...'
```

**Étape 3 — Wrapper shell** `~/bin/claude-max` (chmod +x) :

```bash
#!/bin/bash
set -euo pipefail
VKEY=$(security find-generic-password -a "$USER" -s litellm-claude-code-vkey -w)
export ANTHROPIC_BASE_URL="http://localhost:8092"
export ANTHROPIC_MODEL="anthropic-claude"
export ANTHROPIC_CUSTOM_HEADERS="x-litellm-api-key: Bearer $VKEY"
exec claude "$@"
```

Pourquoi un wrapper et pas `settings.local.json` ? Claude Code `apiKeyHelper` ne pilote QUE l'`Authorization` header (réservé OAuth Max). La virtual key LiteLLM doit aller dans `x-litellm-api-key` via `ANTHROPIC_CUSTOM_HEADERS`, qui n'a pas de mécanisme helper — donc l'env doit être set avant `claude`.

**Étape 4 — Login Max** : `claude-max` → menu "Claude account with subscription" → browser → Authorize → success. Claude Code stocke l'OAuth token et l'envoie comme `Authorization: Bearer <oauth_token>`. LiteLLM le forward à Anthropic.

**Flux des headers (pattern B) :**

| Header                              | Rôle                                         | Géré par                         |
| ----------------------------------- | -------------------------------------------- | -------------------------------- |
| `x-litellm-api-key: Bearer sk-...`  | Auth gateway, tracking, budgets, rate limits | LiteLLM                          |
| `Authorization: Bearer <oauth_max>` | Auth subscription Max                        | Anthropic (forwarded by LiteLLM) |

**Vérification** : `http://127.0.0.1:8092/ui` → Logs → la requête doit montrer `Key Name: claude-code-max`, `Model: anthropic/claude-sonnet-4-...`, et un statut `Success`.

### Troubleshooting

| Symptôme                                              | Cause probable                                                                                                                      | Fix                                                                                                                                                                                                               |
| ----------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 401 Anthropic en pattern B                            | `forward_client_headers_to_llm_api` manquant ou `false`                                                                             | Activer dans `general_settings` ou `model_group_settings`                                                                                                                                                         |
| 401 LiteLLM                                           | `x-litellm-api-key` absent ou expiré                                                                                                | `curl /key/info -H "Authorization: Bearer sk-..."` pour valider                                                                                                                                                   |
| Model not found                                       | `ANTHROPIC_MODEL` ne matche pas `model_name` du proxy                                                                               | `curl /v1/models -H "Authorization: Bearer sk-..."` pour lister                                                                                                                                                   |
| Login Max échoue mais Claude Code marche en pattern A | `ANTHROPIC_BASE_URL` pointe vers LiteLLM mais `apiKeyHelper` injecte la master key sur `Authorization` → conflit avec le flow OAuth | Pour login Max : utiliser le wrapper `claude-max` SANS `apiKeyHelper`, et dans le `settings.local.json` du projet retirer `apiKeyHelper`/`model` (ou utiliser un projet dédié sans `settings.local.json` LiteLLM) |
