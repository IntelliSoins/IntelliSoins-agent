---
paths:
  - "**/litellm*memory*"
  - "**/memory*litellm*"
---

# LiteLLM `/v1/memory` — Persistent Key-Value Store

Endpoint built-in du Proxy LiteLLM (>= v1.83.10) qui expose un store key-value persistant adosse a Postgres. Conçu pour donner a un LLM une **memoire cross-session** (preferences utilisateur, playbooks team, working memory d'agent) sans ecrire ta propre table. Scoping automatique par API key (RBAC) et key globally unique → utiliser des prefixes pour namespacer.

## Matrice des features

| Feature              | Status | Notes                                                            |
| -------------------- | ------ | ---------------------------------------------------------------- |
| Persistance Postgres | ✓      | Backend = la meme DB que LiteLLM (`DATABASE_URL`)                |
| Scoping par API key  | ✓      | user / team_admin / proxy_admin (cf. table plus bas)             |
| Metadata JSON        | ✓      | Champ `metadata` libre, indexable cote Postgres                  |
| List by prefix       | ✓      | `?key_prefix=user:`                                              |
| Atomic upsert (PUT)  | ✓      | Cree ou ecrase, pas de merge automatique                         |
| TTL natif            | ✗      | Pas d'expiration auto — gerer cote app si besoin (cron `DELETE`) |
| Versioning natif     | ✗      | Stocker `version` dans `metadata` si requis                      |

## Pre-requis

- LiteLLM `v1.83.10+` (CHANGELOG : "Memory Management API")
- `DATABASE_URL` Postgres configuree (skill `litellm-proxy-setup`)
- **Aucune config YAML** — l'endpoint est expose des qu'un master key + DB sont presents

> **Stack locale Michael (`http://127.0.0.1:8092`)** : LiteLLM Proxy + Postgres17 deja branche (cf. `litellm-proxy-setup` + auto-memory `~/.claude/projects/-Users-michaelahern-ai-servers/memory/project_litellm_gateway.md`). L'endpoint `/v1/memory` est disponible des `litellm --version` >= 1.83.10. Verifier : `curl -s http://127.0.0.1:8092/health/readiness | jq` puis tester un POST.

## Quick Start

### Create

```shell
curl -X POST "http://localhost:4000/v1/memory" \
  -H "Authorization: Bearer sk-1234" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "user:preferences",
    "value": "Prefers concise responses. Timezone: PST.",
    "metadata": {"version": 1}
  }'
```

```python
import httpx

client = httpx.Client(
    base_url="http://localhost:4000",
    headers={"Authorization": "Bearer sk-1234"},
)

client.post("/v1/memory", json={
    "key": "user:preferences",
    "value": "Prefers concise responses. Timezone: PST.",
    "metadata": {"version": 1},
})
```

### Read

```shell
curl "http://localhost:4000/v1/memory/user:preferences" \
  -H "Authorization: Bearer sk-1234"
```

Retourne `404` si la cle n'existe pas (handle cote client — cf. exemple Slack plus bas).

### Update

PUT est un **upsert**. Ecrase entierement `value` et `metadata` — pas de merge JSON. Pour incrementer une liste, lire d'abord puis re-PUT.

```shell
curl -X PUT "http://localhost:4000/v1/memory/user:preferences" \
  -H "Authorization: Bearer sk-1234" \
  -H "Content-Type: application/json" \
  -d '{"value": "Prefers concise responses. Timezone: EST."}'
```

### List

```shell
# Toutes les entrees visibles par la cle
curl "http://localhost:4000/v1/memory" \
  -H "Authorization: Bearer sk-1234"

# Filtre par prefix (essentiel pour multi-tenant)
curl "http://localhost:4000/v1/memory?key_prefix=user:" \
  -H "Authorization: Bearer sk-1234"
```

### Delete

```shell
curl -X DELETE "http://localhost:4000/v1/memory/user:preferences" \
  -H "Authorization: Bearer sk-1234"
```

## Access Control

Le scoping est **automatique** selon le role de la API key utilisee (cf. skill `litellm-authentication`). Aucune config supplementaire.

| Role                              | Reads              | Writes             |
| --------------------------------- | ------------------ | ------------------ |
| User (virtual key sans `team_id`) | Own + team entries | Own entries only   |
| Team admin                        | Own + team entries | Own + team entries |
| Proxy admin (`master_key`)        | All                | All                |

> **Implication multi-tenant** : une virtual key utilisateur ne peut pas ecrire `team:*` — la creation team-scoped requiert un `team_admin`. Pour les playbooks partages, generer une virtual key team_admin (skill `litellm-authentication`).

## Key Naming — namespacing par prefix

Les cles sont **globalement uniques** dans la DB Postgres LiteLLM. Sans prefix, deux apps qui ecrivent `preferences` se collisionnent. Convention recommandee :

```
user:preferences           → per-user settings
user:{user_id}:profile     → profil specifique a un user_id app-side
team:playbook:onboarding   → ressources team partagees
team:{team_id}:guidelines  → guidelines par team
agent:memory:scratchpad    → working memory d'agent
agent:{agent_name}:state   → etat d'un agent specifique
session:{session_id}:notes → notes de session ephemeres (gerer TTL via cron)
```

Le prefix matters parce que **`?key_prefix=` est la seule maniere de query un sous-ensemble** (pas de full-text search natif). Choisis-le avant prod.

## Patterns d'usage

### 1. Per-user preferences dans un Slack bot

Partition par workspace + user pour isoler les preferences :

```python
import httpx

LITELLM_BASE = "http://localhost:4000"
LITELLM_KEY = "sk-1234"

def memory_key(team_id: str, user_id: str) -> str:
    return f"slack:{team_id}:{user_id}"

async def get_preferences(team_id: str, user_id: str) -> str:
    """Lit les preferences sauvegardees. Retourne '' si rien."""
    key = memory_key(team_id, user_id)
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{LITELLM_BASE}/v1/memory/{key}",
            headers={"Authorization": f"Bearer {LITELLM_KEY}"},
        )
    if r.status_code == 404:
        return ""
    return r.json().get("value", "")

async def save_preference(team_id: str, user_id: str, note: str):
    """Ajoute une preference. PUT upsert — lire-puis-ecrire pour append."""
    key = memory_key(team_id, user_id)
    existing = await get_preferences(team_id, user_id)

    bullets = [b for b in existing.split("\n") if b.strip()]
    bullets.append(f"- {note}")

    async with httpx.AsyncClient() as client:
        await client.put(
            f"{LITELLM_BASE}/v1/memory/{key}",
            headers={"Authorization": f"Bearer {LITELLM_KEY}"},
            json={"value": "\n".join(bullets)},
        )
```

Injection dans le system prompt a chaque tour :

```python
prefs = await get_preferences(team_id, user_id)

messages = [
    {"role": "system", "content": f"""You are a helpful assistant.

SAVED USER PREFERENCES:
{prefs}

Follow these unless the current message contradicts them."""},
    {"role": "user", "content": user_message},
]
```

Lister les preferences d'un workspace entier :

```shell
curl "http://localhost:4000/v1/memory?key_prefix=slack:T024BE7LD:" \
  -H "Authorization: Bearer sk-1234"
```

### 2. Agent scratchpad cross-tour

Working memory persistante entre tool calls / sessions. Penser **etat compresse**, pas log brut (sinon Postgres explose).

```python
SCRATCHPAD_KEY = f"agent:{agent_id}:scratchpad"

# Recuperer en debut de tour
state = (await client.get(f"/v1/memory/{SCRATCHPAD_KEY}")).json().get("value", "{}")
state = json.loads(state)

# Mettre a jour apres l'action
state["last_search"] = {"query": q, "results_top3": top3, "ts": now()}
state["facts_known"].append(new_fact)

# Persister (entire object, pas de partial update natif)
await client.put(
    f"/v1/memory/{SCRATCHPAD_KEY}",
    json={"value": json.dumps(state), "metadata": {"version": state["version"] + 1}},
)
```

### 3. Team playbook partage

```shell
# Creation par un team_admin
curl -X POST "http://localhost:4000/v1/memory" \
  -H "Authorization: Bearer sk-team-admin-..." \
  -d '{
    "key": "team:onboarding:checklist",
    "value": "1. Setup VPN\n2. Generate virtual key\n3. ...",
    "metadata": {"owner": "ops", "last_updated": "2026-05-10"}
  }'

# Lecture par n'importe quel membre du team
curl "http://localhost:4000/v1/memory/team:onboarding:checklist" \
  -H "Authorization: Bearer sk-user-member-..."
```

## Metadata

Champ JSON arbitraire pour tagger / versionner. Stocke avec la valeur, retourne au GET.

```json
{
  "key": "agent:findings",
  "value": "Q1 API usage up 15%...",
  "metadata": {
    "tags": ["research", "metrics"],
    "confidence": 0.92,
    "version": 3,
    "updated_at": "2026-05-10T12:00:00Z"
  }
}
```

Patterns utiles cote `metadata` :

- `version` int → detecter staleness avant overwrite
- `expires_at` ISO date → expiration cote app (pas de TTL natif — voir limitations)
- `tags` array → categoriser pour filtrage cote app (Postgres JSONB queryable directement si tu vises le DB)

## Limitations a connaitre avant prod

| Limite                                    | Workaround                                                                                                              |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Pas de TTL natif                          | Cron `DELETE` periodique ou cron app-side qui purge selon `metadata.expires_at`                                         |
| Pas de partial update (`PUT` ecrase tout) | Read-then-write pattern (voir Slack bot ex.) → races possibles si concurrent                                            |
| Pas de full-text search                   | Filtrer par `key_prefix` puis grep cote client. Pour FTS reel : query Postgres directement (`pg_trgm`, GIN sur `value`) |
| Cle globalement unique                    | Toujours prefixer (`user:`, `team:`, `agent:`) — sinon collisions cross-app                                             |
| Pas de pagination documentee a date       | Surveiller la taille des LIST par prefix; si > 10k entries, query Postgres direct                                       |
| Pas de versioning natif                   | Stocker `version` dans `metadata` + check avant overwrite                                                               |
| Concurrent writes (race)                  | Si 2 processus PUT la meme cle simultanement, le dernier gagne. Pour counters / append : envisager Redis a la place     |

## Loi 25 / IntelliSoins — gating PHI

> **Critique pour IntelliSoins** : le store memoire vit dans la DB Postgres LiteLLM. Avant d'ecrire **toute donnee patient (PHI)**, verifier :
>
> 1. **Residency** : la DB Postgres LiteLLM est-elle au Canada ? Pour le VPS OVH BHS5 (Beauharnois, QC), oui. Pour un proxy LiteLLM cloud-hoste US, **non** → ne pas stocker PHI.
> 2. **Encryption at rest** : Postgres encrypte (LUKS / pgcrypto / SOPS pour secrets seulement) — verifier avant d'activer.
> 3. **Consent art.14 (Loi 25)** : si `value` contient des donnees personnelles ou PHI, verifier que `UserConsent.ai_processing = true` cote app **avant** le POST. Cf. memory `topic-loi25-consent.md` (TASK-158, middleware `checkConsentMiddleware`).
> 4. **Retention art.5** : pas de TTL natif → ajouter une purge planifiee equivalente a `cron-trace-logs-cleanup.yml` (30j) si tu stockes des donnees identifiantes.
> 5. **Drift residency** : auto-memory `topic_data_residency_canada_llm.md` recense les providers conformes. Si tu utilises LiteLLM hosted ailleurs, drift Loi 25.
>
> Pour des donnees **non-patient** (preferences UI, agent scratchpad d'orchestration interne), le risque est faible et `/v1/memory` est OK tel quel.

## Debugging

### 401 Unauthorized

La virtual key est invalide ou revoquee. Verifier `/key/info` :

```shell
curl http://localhost:4000/key/info -H "Authorization: Bearer sk-..."
```

### 403 Forbidden

La cle existe mais n'a pas le scope. Ex : virtual key user qui essaie d'ecrire `team:*`. Promouvoir au role team_admin (`/key/update` ou regenerer).

### 404 Not Found sur GET

Cle inexistante. Code attendu — handle cote client (`return ""` ou default).

### 500 Internal Server Error

Generalement Postgres down ou DATABASE_URL mal configuree. Verifier `/health/readiness`.

### Empty list inattendue

L'API filtre **automatiquement** par scope de la cle utilisee. Avec une virtual key user, tu ne verras pas les `team:*` ni les `proxy:*`. Tester avec le `master_key` pour confirmer que c'est un probleme de scope et pas de creation.

## Cross-references

- **`litellm-authentication`** — generer virtual keys avec roles user / team_admin pour pouvoir ecrire `team:*`
- **`litellm-proxy-setup`** — pre-requis Postgres + master_key
- **`litellm-config-yaml`** — aucun changement requis pour activer memory (built-in)
- **`litellm-overview`** — entry point gateway
- **`litellm-caching`** — pour cache LLM responses (different — ttl-based, transparent), memory est pour data utilisateur explicite

## API Reference

Schemas de requete/reponse, error codes : <https://docs.litellm.ai/docs/memory_management>.
