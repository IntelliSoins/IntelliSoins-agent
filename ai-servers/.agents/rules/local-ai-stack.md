---
paths:
  - "~/ai-servers/**"
  - "**/*litellm*"
  - "**/*aictl*"
  - "**/litellm*.yaml"
  - "**/litellm*.yml"
  - "**/.config/aictl/**"
  - "**/servers.yaml"
---

# Local AI Stack — Conventions d'appel (Host macOS personnel)

Stack AI/ML **personnelle** Michael Ahern, **installée nativement sur le disque** (Apple Silicon M3 Max via Homebrew + LaunchAgents + MLX). Couvre LiteLLM Proxy AI Gateway local (:8092), sidecar vector store pgvector (:8093), aictl + serveurs MLX, omlx multi-modèle (:8211), conventions d'appel des modèles, et config Claude Code `settings.local.json`. Charger quand un projet mentionne "ai-servers", "aictl", "MLX", "LiteLLM Proxy host", "qwen3", "medgemma", "nemotron", "gemma4", "embedding local", "reranker local", "ANTHROPIC_BASE_URL", "apiKeyHelper", "omlx", "Continue VS Code", "PRO-G40", "local servers", "port 8092".

## Périmètre — Deux stacks distincts, NE PAS confondre

| Critère              | **Stack perso (cette rule)**                                                                        | **Stack Docker IntelliSoins (autres rules)**                                                                                    |
| -------------------- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **But**              | Usage personnel : Continue VS Code, Claude Code harness, scripts Python locaux, expérimentation MLX | Application IntelliSoins (web app médicale en production)                                                                       |
| **Hôte**             | macOS host (Apple Silicon M3 Max)                                                                   | Containers Docker (Mac local :4000 ou VPS OVH)                                                                                  |
| **Installation**     | Homebrew, MLX natif, LaunchAgents (`aictl install`), binaires sur disque                            | `docker compose up`, images registry Forgejo                                                                                    |
| **LiteLLM Proxy**    | `:8092` natif sur 127.0.0.1, géré par LaunchAgent                                                   | LiteLLM dans container Docker (`docker-compose.vps.yml`, voir `litellm.md`)                                                     |
| **Config**           | `~/ai-servers/servers.yaml`, `~/ai-servers/litellm-proxy/config.yaml`                               | `litellm/*.yaml`, `docker-compose*.yml`, secrets SOPS                                                                           |
| **Modèles**          | MLX (`mlx-openai-server`, `vllm-mlx`), omlx, Ollama brew                                            | Qwen3.5-35B vLLM/SGLang GPU OVH, MedGemma vision via LiteLLM/FastAPI BHS5                                                       |
| **Authentification** | Master key Keychain macOS (`security find-generic-password`)                                        | Virtual keys LiteLLM (DB Postgres), SOPS-encrypted secrets                                                                      |
| **Rules associées**  | Cette rule (`local-ai-stack.md`)                                                                    | `litellm.md` + `litellm/*.md`, `ovh.md` (index) + `ovh/gpu-bhs5.md` + `ovh/ai-endpoints.md`, `vps-infrastructure.md`, `cicd.md` |

**Règle d'or** : ne JAMAIS pointer une config de l'application IntelliSoins (`.env*`, `docker-compose*.yml`, code applicatif `src/**`) vers `127.0.0.1:8092` (proxy perso macOS). Les containers Docker ont leur propre proxy LiteLLM ; mélanger les deux casse l'isolation, le tracking spend, et empêche le deploy VPS.

**Réciproquement** : ne pas configurer le stack perso (`~/ai-servers/litellm-proxy/config.yaml`) pour appeler des services internes Docker IntelliSoins (`http://app:3000`, `http://litellm:4000` dans le réseau Docker). Ces deux stacks vivent dans des espaces réseau différents.

## aictl — Référence rapide

| Commande               | Action                                               |
| ---------------------- | ---------------------------------------------------- |
| `aictl status`         | Table live : PID, port, RAM, uptime                  |
| `aictl health`         | HTTP health checks sur tous les ports                |
| `aictl list`           | Registre des serveurs (nom, port, catégorie, disque) |
| `aictl start <name>`   | Démarrer un serveur                                  |
| `aictl stop <name>`    | Arrêter un serveur                                   |
| `aictl restart <name>` | Stop + start                                         |
| `aictl start all`      | Démarrer tous les serveurs                           |
| `aictl logs <name>`    | `tail -f` des logs serveur                           |
| `aictl install`        | Régénérer les LaunchAgents depuis servers.yaml       |
| `aictl uninstall`      | Supprimer tous les LaunchAgents                      |

`aictl` non trouvé → `ln -sf ~/ai-servers/aictl ~/.local/bin/aictl`

## Inventaire des serveurs

Source de vérité = `~/ai-servers/servers.yaml` (lire avant toute affirmation). **18 entrées** gérées par aictl + **omlx** externe (brew, :8211). Ollama retiré (2026-07-06).

| Catégorie    | Serveur                   | Port      | Modèle / Notes                                          |
| ------------ | ------------------------- | --------- | ------------------------------------------------------- |
| Gateway      | litellm-proxy             | :8092     | LiteLLM AI Gateway DB-backed, master key Keychain       |
| LLM externe  | **omlx**                  | **:8211** | Multi-modèles (Qwen3.6, Qwen3-Coder, Gemma4…), brew     |
| Vector store | litellm-pgvector          | :8093     | Sidecar OpenAI Vector Stores API, Postgres17 + pgvector |
| Vector store | litellm-pgvector-openclaw | :8100     | Sidecar pgvector dédié OpenClaw                         |
| Embedding    | embedding                 | :8084     | Qwen3-Embedding-0.6B 1024D                              |
| Reranker     | reranker                  | :8085     | BGE-reranker-v2-m3                                      |
| NER          | gliner                    | :8091     | GLiNER Biomed, PyTorch CPU                              |
| OCR          | docling                   | :5010     | Docling                                                 |
| STT          | whisper-stt               | :2022     | Whisper large-v3-turbo (LoRA voix Michael)              |
| TTS          | voxcpm-tts                | :8025     | VoxCPM2 Michael v6 MLX 8bit                             |
| TTS          | voxcpm-openai-bridge      | :8883     | Pont OpenAI-compatible → OpenClaw TTS                   |
| Translation  | translation               | :6060     | NLLB-200                                                |
| VLM          | mlx-vlm-omni              | :8089     | Gemma 4 12B omni (démarrage manuel, contrôle RAM)       |
| App          | study-chat-bridge         | :8765     | Pont fiches concept-interactif                          |
| App          | litellm-config-sync       | —         | Sync config/UI LiteLLM                                  |
| App          | openclaw                  | :18789    | Gateway IntelliSoins                                    |
| App          | signal-api                | :8094     | Signal Messenger REST API (autostart off)               |
| App          | signal-agent-router       | :8096     | Signal Agent Router                                     |

Config : `~/ai-servers/servers.yaml` (source de vérité). LaunchAgents : `~/Library/LaunchAgents/com.ai-servers.*`.

Backends MLX standalone retirés — voir `litellm-proxy/standby-models.yaml`.

## PRO-G40 Disque externe

SSD `/Volumes/PRO-G40/.cache/huggingface/` — optionnel pour caches HF volumineux. Les serveurs actifs (`embedding`, `reranker`, etc.) tournent sans dépendance disque stricte dans `servers.yaml` (2026-07-06).

## omlx — LLM local multi-modèle (:8211)

Serveur LLM Apple Silicon (jundot/omlx) avec **tiered KV cache** (RAM + SSD), API OpenAI + Anthropic natives, menubar app + admin web. Géré par Homebrew, **pas via aictl**.

```bash
brew services start omlx       # auto-restart au reboot
brew services stop omlx
brew services restart omlx
curl -s -H "Authorization: Bearer $(jq -r .auth.api_key ~/.omlx/settings.json)" \
  http://127.0.0.1:8211/v1/models | python3 -m json.tool
```

Modèles typiques : `Qwen3.6-35B-A3B-4bit` (général), `Qwen3-Coder-30B-A3B-Instruct-4bit` (code), `mlx-community--gemma-4-12B-it-8bit` (Gemma 4).

Logs : `$(brew --prefix)/var/log/omlx.log` + `~/.omlx/logs/server.log`.
Rule détaillée : `~/.claude/rules/omlx.md`.

**LiteLLM** : aliases `general-local`, `code-local`, `gemma4-12b` routent vers oMLX :8211 via le hub :8092.

## Continue VS Code — stack 100% local

Config `~/.continue/config.yaml` routée sur ports locaux, zéro cloud.

| Rôle                | Port  | Modèle                          | Backend              |
| ------------------- | ----- | ------------------------------- | -------------------- |
| chat / edit / apply | :8092 | `code-local` ou `general-local` | LiteLLM → oMLX :8211 |
| embed               | :8084 | Qwen/Qwen3-Embedding-0.6B       | aictl embedding      |
| rerank              | :8085 | BAAI/bge-reranker-v2-m3         | aictl reranker       |

Pour FIM/autocomplete direct oMLX : `:8211` (modèle `Qwen3-Coder-30B-A3B-Instruct-4bit`).

## Toujours router via le LiteLLM Proxy (host perso uniquement)

URL : `http://127.0.0.1:8092/v1` (OpenAI-compatible) — port 8092 sur 127.0.0.1. **C'est le proxy LiteLLM personnel installé sur le disque macOS**, pas celui de l'application IntelliSoins en Docker (cf. section Périmètre ci-dessus).

Master key : `security find-generic-password -a "$USER" -s litellm-master-key -w`
(macOS Keychain. JAMAIS hardcoder, JAMAIS écrire dans .env d'un projet — ni perso, ni IntelliSoins.)

**Ne pas** appeler directement `127.0.0.1:8080-8089` (ports MLX) — perte de spend tracking, cache, fallbacks.

**Ne pas confondre** avec le LiteLLM IntelliSoins Docker (port et auth différents, voir `litellm.md`).

## LiteLLM Gateway — état réel

Proxy **DB-backed** (pas minimal) : `master_key`, `database_url`, `salt_key`, rétention spend logs et `disable_master_key_return` dans `litellm-proxy/config.yaml`. La DB `litellm` porte virtual keys, users, budgets et spend logs ; Redis db `1` sert le cache ; `vector_store_registry` → `litellm-pgvector` :8093.

Vérification :

```bash
cd ~/ai-servers && ./aictl status && ./aictl health
MASTER=$(security find-generic-password -a "$USER" -s litellm-master-key -w)
curl -s :8092/v1/models -H "Authorization: Bearer $MASTER" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)["data"]),"modèles exposés")'
redis-cli -n 1 ping
```

## Modèles et aliases LiteLLM

`config.yaml` = **49 `model_name`** statiques ; le proxy DB-backed expose **~63 live** (`curl :8092/v1/models` — l'écart = entrées ajoutées via l'Admin UI).

| model_name / alias                                                                       | Type                           |
| ---------------------------------------------------------------------------------------- | ------------------------------ |
| `general-local`, `code-local`, `Qwen3.6-35B-A3B-4bit`                                    | LLM local via oMLX :8211       |
| `gemma4-12b`, `gemma4-12b-mlx`, `voice-local`                                            | Gemma 4 via oMLX :8211         |
| `qwen3-embedding` (1024D), `bge-reranker-v2-m3`                                          | Embedding / Rerank             |
| `whisper-stt`                                                                            | STT :2022                      |
| `gpt-5.5`, `gpt-4o`                                                                      | Cloud OpenAI                   |
| `deepseek-v3.1`, `deepseek-r1`, `qwen3-235b`, `qwen3-coder-480b`, `glm-5.1`, `kimi-k2.6` | Together AI (cloud US)         |
| `claude-local-*`                                                                         | Aliases Claude Code → locaux   |
| `claude-together-*`, `claude-openai-*`                                                   | Aliases Claude Code → cloud    |
| `anthropic-claude-*`, `vertex-claude-*`                                                  | Anthropic API / Vertex via hub |

**Standby** (ports MLX retirés) : `medgemma-27b`, `qwen3-email`, `nemotron-30b`, `qwen35-35b`, `gemma4-e4b`, etc. — voir `litellm-proxy/standby-models.yaml`. Ollama retiré 2026-07-06.

**Together AI caveats** :

- Modèles de reasoning (`kimi-k2.6`, `deepseek-r1`) consomment des tokens en `reasoning_content` : prévoir `max_tokens` ≥ 80 sinon `content` revient vide.
- 6/6 modèles testés OK en serverless (Ottawa retourné). Voir `~/ai-servers/litellm-proxy/config.yaml:107-138`.

## Pattern Python recommandé

```python
import subprocess
from openai import OpenAI

def litellm_client():
    master = subprocess.check_output([
        "security", "find-generic-password",
        "-a", "michaelahern", "-s", "litellm-master-key", "-w"
    ]).decode().strip()
    return OpenAI(base_url="http://127.0.0.1:8092/v1", api_key=master)
```

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

## Troubleshooting rapide

| Symptôme                        | Cause probable                     | Fix                                                                                                   |
| ------------------------------- | ---------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Serveur DOWN, pas de PID        | Crash ou pas démarré               | `aictl restart <name>`                                                                                |
| Health retourne 000             | Pas en cours d'exécution           | Vérifier logs, `aictl restart <name>`                                                                 |
| Tous les serveurs PRO-G40 DOWN  | Disque non monté                   | Monter le disque, KeepAlive redémarre auto                                                            |
| Conflit de port                 | Autre process sur le même port     | `lsof -i TCP:<port>` pour identifier                                                                  |
| `aictl` non trouvé              | Symlink manquant                   | `ln -sf ~/ai-servers/aictl ~/.local/bin/aictl`                                                        |
| LaunchAgent introuvable         | Pas installé                       | `aictl install`                                                                                       |
| Master key manquante (keychain) | Clé non créée ou service différent | `security find-generic-password -a "$USER" -s litellm-master-key -w` (message d'erreur = clé absente) |

## Caveats serveurs MLX — exceptions au routage LiteLLM

### Serveur GLiNER `:8091` — IGNORE le param `labels` (`Ihor/gliner-biomed-large-v1.0`)

Le modèle biomédical fine-tuné retourne **ses labels d'entraînement** peu importe ce que la requête HTTP demande. Validé 2026-05-11 :

```bash
curl -X POST http://localhost:8091/extract -d '{"text":"...","labels":["Drug","Disease"],"threshold":0.3}'
# Retourne quand même: Lab test, Clinical finding, Drug dosage, Drug frequency,
# Duration of treatment, Adverse effect, Author, Institution, Medical procedure,
# Demographic information, Study type
```

**Implication** : ne pas se fier au filtrage côté serveur. Filtrer **côté client** après extraction si le pipeline en aval ne sait pas mapper tous les labels (cf. désynchro mapping SQL ci-dessous).

### Embeddings MLX `:8084` — bypass autorisé si bug tiktoken

Connecter `langchain-openai` `OpenAIEmbeddings` à n'importe quel endpoint OpenAI-compat non-OpenAI (LiteLLM :8092 OU MLX :8084 direct) déclenche un bug : `check_embedding_ctx_length=True` (défaut) active tiktoken qui pré-tokenise les inputs en `int[]` côté client. Le serveur MLX rejette avec HTTP 422 `Input should be a valid string`.

Deux fixes valides :

| Fix                                                                       | Pour                                             | Contre                                                                     |
| ------------------------------------------------------------------------- | ------------------------------------------------ | -------------------------------------------------------------------------- |
| `OpenAIEmbeddings(base_url=":8092/v1", check_embedding_ctx_length=False)` | Garde routage LiteLLM (spend tracking, fallback) | Dépendance à un flag interne langchain                                     |
| Bypass `:8084` direct via wrapper natif (cf. section RAGAs ci-dessous)    | Contrôle total, pas de magie tiktoken            | Perd le spend tracking embeddings (acceptable : haut volume / faible coût) |

**Exception explicite à l'anti-pattern #1** ("hardcoder ports MLX") : bypass `:8084` toléré **uniquement** pour les embeddings quand on parle à RAGAs / sentence-transformers / un client custom qui n'a pas besoin du tracking.

## Pattern — Wrapper RAGAs natif pour MLX (sans langchain-openai)

Pour utiliser RAGAs avec un serveur MLX local, **subclasser directement** `BaseRagasEmbeddings` au lieu de `LangchainEmbeddingsWrapper(OpenAIEmbeddings(...))`. Évite le bug tiktoken, ~30 lignes, réutilisable pour BGE rerank et tout serveur OpenAI-compat.

```python
from ragas.embeddings.base import BaseRagasEmbeddings
from ragas.run_config import RunConfig
import httpx

class MlxHttpEmbeddings(BaseRagasEmbeddings):
    def __init__(self, base_url="http://localhost:8084",
                 model="Qwen/Qwen3-Embedding-0.6B", batch_size=16):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.batch_size = batch_size
        self.run_config = RunConfig()
        self._sync = httpx.Client(timeout=60.0)
        self._async = None  # lazy init

    def set_run_config(self, rc: RunConfig): self.run_config = rc

    def _post_sync(self, texts):
        r = self._sync.post(f"{self.base_url}/v1/embeddings",
                            json={"input": texts, "model": self.model})
        r.raise_for_status()
        return [d["embedding"] for d in r.json()["data"]]

    def embed_documents(self, texts):
        out = []
        for i in range(0, len(texts), self.batch_size):
            out.extend(self._post_sync(texts[i:i+self.batch_size]))
        return out
    def embed_query(self, text): return self._post_sync([text])[0]
    # aembed_documents / aembed_query : symétriques avec httpx.AsyncClient
```

**Implémentation de référence** : `~/ai-servers/scripts/mlx_embeddings_client.py` (testée 2026-05-11 sur ragas 0.2.10 + Python 3.12).

**Cohérence d'espace d'embedding** : critique. Si la DB cible utilise un modèle pour indexer ses chunks (ex: `Qwen/Qwen3-Embedding-0.6B` 1024D sur `:8084` pour `document_embeddings.embedding halfvec(1024)`), le wrapper RAGAs doit utiliser **exactement le même modèle**. Sinon les métriques `context_precision` et `context_recall` mesurent des espaces différents.

## Smoke tests `kg_pipeline.medical` (2026-05-11)

### Pipeline

DB `medical`, schema `kg_pipeline.*`. La fonction `run_chunk(chunk_id, ner_threshold=0.5, promote_age=true)` orchestre :
NER GLiNER (:8091) → linking embeddings (:8084) → edge candidates → BGE rerank (:8085) → promotion `public.kg_relations` + Apache AGE `medical_graph`.

### Résultats RAGAs

| Type de chunk                                                                | Edges générés / 3 chunks | Edges promus | Faithfulness               | ResponseRelevancy |
| ---------------------------------------------------------------------------- | ------------------------ | ------------ | -------------------------- | ----------------- |
| **Meta-discours** (deprescription guidelines, NCQA, Beers méta)              | 1                        | 0            | 0.07                       | 0.23              |
| **PubMed cliniques** (gabapentin, pregabalin, oxycodone, analgésiques RI/RH) | 29                       | 8            | NaN (bug max_tokens judge) | 0.48              |

**Promotion precision clinique vérifiée manuellement** : ~12.5% (1 promue sur 8 est factuellement correcte).

### Bugs identifiés dans le pipeline

| Bug                               | Description                                                                                                                                                                                                                                                                | Impact                                             |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| **RE combinatoire**               | `process_chunk` génère des paires `(source, target)` sans analyse syntaxique. Sur "Pregabalin reduces morphine's nausea", extrait `gabapentin → nausea` au lieu de `morphine → nausea`.                                                                                    | Attribution AE au mauvais drug                     |
| **Tokenisation NER**              | `Pregabalin` parfois découpé en `Pregabalin` + `prega` (entité fantôme avec score 0.7+)                                                                                                                                                                                    | Edges parasites `prega → ...`                      |
| **Pas de validation ontologique** | Promeut `oxycodone -[BELONGS_TO_CLASS]-> non-steroidal anti-inflammatory drugs` (faux, oxycodone = opioïde)                                                                                                                                                                | Relations cliniquement fausses dans `kg_relations` |
| **Désynchro labels SQL**          | `kg_pipeline.entity_type_for_label()` mappe 7 labels, le serveur GLiNER en retourne 11+. `Drug dosage`, `Drug frequency`, `Clinical finding`, `Lab test value`, `Duration of treatment` sont **détectés mais jetés** (`entity_type IS NULL` → pas de linking → pas d'edge) | ~40% du signal NER perdu                           |

### Verdict architectural

**Ne pas intégrer `kg_pipeline.medical` comme source directe d'un KG curé en production** (ex: IntelliSoins `medical_graph` prod). Précision 12.5% sur relations promues = contamination du KG par des faits faux.

**Usage acceptable** : mode `candidate-only` — le pipeline produit des candidats, une couche d'évaluation LLM (Haiku RE, validation ontologique) les filtre avant promotion. Économise ~70% de l'effort RE LLM vs génération from scratch, garde la garantie de qualité.

## Skills & rules associés

- `intellisoins-infrastructure:local-ai-servers` — gestion aictl + servers.yaml
- `intellisoins-litellm:*` — 9 skills LiteLLM (proxy-setup, config-yaml, routing, cache, budgets, etc.)
- `intellisoins-mlx:*` — 50+ skills MLX (modèles spécifiques, fine-tuning, etc.)
- **Rules moteurs d'inférence** (converties des skills 2026-05-24) : `vmlx.md`, `vllm-mlx.md` (backend chat `:8089`), `vllm-metal.md`, `turboquant-mlx.md` (KV compression, actif sur medgemma-27b `:8080`) — backends MLX de cette stack. `vllm-omni.md` existe aussi mais cible GPU/NPU Linux → **hors stack Mac**.
- `intellisoins-architecture-health:health-check` — monitoring stack

## Anti-patterns à éviter

1. **Hardcoder ports MLX** : `OpenAI(base_url="http://127.0.0.1:8080/v1")` → utiliser le proxy
2. **Stocker master key dans .env de projet** : utiliser Keychain
3. **Appeler un modèle sans `aictl start` préalable** : MLX DOWN par défaut
4. **Modifier directement servers.yaml sans `aictl install`** : LaunchAgents pas régénérés
5. **Coder un fallback custom** : utiliser `router_settings` du proxy

## Ressources

- Config proxy : `~/ai-servers/litellm-proxy/config.yaml`
- Activation/rollback : `~/ai-servers/litellm-proxy/ACTIVATION.md`
- Logs : `~/ai-servers/logs/litellm-proxy.log`
- Admin UI : `http://127.0.0.1:8092/ui`
