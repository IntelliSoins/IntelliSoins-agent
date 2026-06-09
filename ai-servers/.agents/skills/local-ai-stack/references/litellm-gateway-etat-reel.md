## LiteLLM Gateway — état réel

Proxy **DB-backed** (pas minimal) : `master_key`, `database_url`, `salt_key`, rétention spend logs et `disable_master_key_return` dans `litellm-proxy/config.yaml`. La DB `litellm` porte virtual keys, users, budgets et spend logs ; Redis db `1` sert le cache ; `vector_store_registry` → `litellm-pgvector` :8093.

Vérification :

```bash
cd ~/ai-servers && ./aictl status && ./aictl health
MASTER=$(security find-generic-password -a "$USER" -s litellm-master-key -w)
curl -s :8092/v1/models -H "Authorization: Bearer $MASTER" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)["data"]),"modèles exposés")'
redis-cli -n 1 ping
```
