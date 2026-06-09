# Activation LiteLLM Proxy — Etapes manuelles

Configuration preparee le 2026-05-01. A executer quand pret a activer le proxy.

## Note importante sur Postgres17 + LaunchAgent

Le briefing initial supposait l'existence d'un plist Homebrew statique
`/opt/homebrew/opt/postgresql@17/homebrew.mxcl.postgresql@17.plist`.
**Ce fichier n'existe pas.** Homebrew genere le plist a la volee lors
de `brew services start`. Aucun plist n'a donc ete copie dans
`~/Library/LaunchAgents/` durant la preparation.

L'autostart au prochain login se configure naturellement avec la commande
ci-dessous (Etape 1 Option A).

## Etape 1 — Demarrer Postgres17

**Option A — Demarrage immediat + persistance au login (recommande)**

```bash
brew services start postgresql@17
```

Cette commande genere le plist Homebrew dans `~/Library/LaunchAgents/`,
demarre Postgres immediatement, et le persiste au login.

**Option B — Demarrage one-shot sans persistance**

```bash
/opt/homebrew/opt/postgresql@17/bin/pg_ctl -D /opt/homebrew/var/postgresql@17 start
```

Verifier que Postgres ecoute :

```bash
lsof -iTCP:5432 -sTCP:LISTEN
```

## Etape 2 — Creer la base `litellm`

```bash
psql -h localhost -U michaelahern -d postgres -c "CREATE DATABASE litellm OWNER michaelahern;"
```

## Etape 3 — Demarrer LiteLLM Proxy

```bash
aictl start litellm-proxy
```

LiteLLM va automatiquement creer ses tables Prisma au premier demarrage.

## Etape 4 — Verifier

```bash
# Recuperer master key depuis Keychain
MASTER=$(security find-generic-password -a "$USER" -s litellm-master-key -w)

# Health
curl http://127.0.0.1:8092/health/liveliness

# Liste des 16 modeles
curl -H "Authorization: Bearer $MASTER" http://127.0.0.1:8092/v1/models | python3 -m json.tool

# Test chat (qwen35-9b-vision est le seul UP confirme)
curl -H "Authorization: Bearer $MASTER" -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8092/v1/chat/completions \
  -d '{"model": "qwen35-9b-vision", "messages": [{"role": "user", "content": "Hello"}], "max_tokens": 10}'

# Admin UI
open http://127.0.0.1:8092/ui  # Login: master key (Keychain)
```

## Etape 5 — Mettre a jour le catalogue PG (optionnel)

Une fois la base `litellm` creee, mettre a jour
`~/.claude/plugins/intellisoins-plugins/intellisoins-postgresql/skills/local-databases-catalog/SKILL.md` :

- Ligne 4 : `20 bases` -> `21 bases`
- Ajouter `litellm` dans la liste alphabetique
- Ajouter ligne dans tableau "Vue d'ensemble"

## Rollback

Si probleme, restaurer :

```bash
mv ~/ai-servers/litellm-proxy/config.yaml.bak ~/ai-servers/litellm-proxy/config.yaml
mv ~/ai-servers/launchers/litellm-proxy.sh.bak ~/ai-servers/launchers/litellm-proxy.sh
security delete-generic-password -a "$USER" -s litellm-master-key
security delete-generic-password -a "$USER" -s litellm-salt-key
# Si Postgres a ete demarre via brew services :
brew services stop postgresql@17
```

## Note importante — Postgres17 et reboot

La formule Homebrew `petere/postgresql/postgresql@17` n'a PAS de service file (`brew services start postgresql@17` retourne `Formula has not implemented #plist`). Au prochain reboot, Postgres ne demarrera PAS automatiquement et LiteLLM echouera.

**Pour demarrer Postgres apres un reboot** :

```bash
/opt/homebrew/opt/postgresql@17/bin/pg_ctl -D /opt/homebrew/var/postgresql@17 -l /opt/homebrew/var/log/postgresql@17.log start
```

**Pour rendre Postgres permanent au login** (action future, hors scope) :

- Soit creer un LaunchAgent custom `~/Library/LaunchAgents/com.michaelahern.postgresql@17.plist` qui invoque `pg_ctl`
- Soit migrer vers la formule `homebrew/core/postgresql@17` qui inclut le service (mais perd `petere/postgresql` extensions custom)
- Soit garder le demarrage manuel post-reboot

**Note Prisma (decouvert 2026-05-01)** : LiteLLM Proxy a besoin du package Python `prisma` ET d'un client genere. Si reinstallation propre du venv :

```bash
VIRTUAL_ENV=/Users/michaelahern/.venvs/litellm uv pip install prisma
cd /Users/michaelahern/.venvs/litellm/lib/python3.12/site-packages/litellm/proxy
PATH=/Users/michaelahern/.venvs/litellm/bin:$PATH /Users/michaelahern/.venvs/litellm/bin/prisma generate
```

Decision laissee a Michael.

## Auto-start Postgres17 — Configure (2026-05-01)

LaunchAgent custom cree : `~/Library/LaunchAgents/com.michaelahern.postgresql@17.plist`

Postgres demarrera automatiquement au prochain login. Les extensions custom de `petere/postgresql` (pgvector 0.8.2, vchord, pg_search, pg_duckdb...) sont preservees car on ne touche pas a la formule.

**Pour tester immediatement** (optionnel) :

```bash
# Arreter le Postgres actuel (lance via pg_ctl manuel ce matin)
/opt/homebrew/opt/postgresql@17/bin/pg_ctl -D /opt/homebrew/var/postgresql@17 stop

# Charger le LaunchAgent (= demarrer via launchd avec KeepAlive)
launchctl load ~/Library/LaunchAgents/com.michaelahern.postgresql@17.plist

# Verifier
launchctl list | grep postgresql
pg_isready -h localhost
```

**Pour desactiver** :

```bash
launchctl unload ~/Library/LaunchAgents/com.michaelahern.postgresql@17.plist
rm ~/Library/LaunchAgents/com.michaelahern.postgresql@17.plist
```

## Robustesse Prisma — Configuree (2026-05-01)

Le launcher `litellm-proxy.sh` detecte si le client Prisma manque (ex: venv recree) et le regenere automatiquement avant de lancer le proxy. Pas d'intervention manuelle requise.
