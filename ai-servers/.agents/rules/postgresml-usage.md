---
name: postgresml-usage
description: Utilisation pgml in-database (embed/chunk/rank/transform/train/predict/tune/decompose) dans n'importe quelle base PG locale. Chargee on-demand quand fichiers pgml/postgresml touches. Hors trigger: ouvrir manuellement via topic pointer dans memory.
paths:
  - "**/pgml*"
  - "**/postgresml*"
  - "**/BUILD-MACOS-NOTES*"
---

# PostgresML — Utilisation dans une base PostgreSQL

Rule globale réutilisable cross-projet pour activer et exploiter le fork
`postgresml-intellisoins` (Rust natif Homebrew, pgrx 0.12.9) dans n'importe quelle
base PostgreSQL locale (catalogue 22 bases PG@17 + Docker).

> **Source de vérité technique** : projet `~/postgresml-build/`. Cette rule en extrait
> la marche à suivre côté **utilisateur** (consommateur d'une DB existante). Pour les
> findings build/patches, voir `pgml-extension/BUILD-MACOS-NOTES.md` (17 findings §1-§17).

## Quand consulter cette rule

- Tu veux ajouter du ML in-database à une base existante (`finances`, `assurance`,
  `medical`, `intelligence_artificielle`, etc. — voir skill `local-databases-catalog`).
- Tu veux savoir **ce que pgml peut faire** sans dépendances externes (Python, REST API).
- Tu veux **un snippet SQL** pour entraînement / prédiction / embeddings / RAG / NLP.
- Tu cherches à comprendre quels modules pgml sont **KO** sur la build locale.

## Stack & prérequis (rappel rapide)

| Composant                  | Valeur                                                                                                                     |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| pgml                       | 2.10.9 fork intellisoins (base upstream `caf2b6c` + patches macOS `ba752636` + sous-système MLX/MLP natif `e4582c91`)      |
| PostgreSQL                 | 17.8 Homebrew petere/postgresql, port 5432                                                                                 |
| Extension installée via    | `cargo pgrx install --release` depuis `~/postgresml-build/pgml-extension`                                                  |
| Python venv                | `/Users/michaelahern/pgml-venv` (torch 2.11 MPS, transformers 5.7, sentence-transformers 5.4.1, datasets 4.8.5, trl 0.9.6) |
| `shared_preload_libraries` | doit contenir `pgml` (déjà fait sur `pgml_test`)                                                                           |

Pour vérifier l'état complet : `BUILD-MACOS-NOTES.md` §1-§17 (matrice capacités OK/KO post-patches).

## Marche à suivre — Activer pgml dans une base existante

Exemple concret : tu es dans la base `finances` et tu veux y ajouter pgml.

### 1. Vérifier que pgml est chargé au démarrage PG

```bash
psql -p 5432 -d postgres -c "SHOW shared_preload_libraries;"
```

Le résultat doit contenir `pgml`. Si absent :

```bash
# Éditer le postgresql.conf de Homebrew
$EDITOR /opt/homebrew/var/postgresql@17/postgresql.conf
# Ajouter ou compléter :
# shared_preload_libraries = 'pgml,pg_duckdb,vchord,pg_cron,vectorize,pg_stat_statements'

# Restart PG (procédure stricte BUILD-MACOS-NOTES.md §11)
brew services restart postgresql@17
```

### 2. Configurer le venv Python pour la base cible

pgml utilise des bindings Python (sklearn, HF transformers, sentence-transformers).
Le venv est partagé via la GUC `pgml.venv`. Deux options :

```sql
-- Option A : par base (recommandé, persiste)
ALTER DATABASE finances SET pgml.venv = '/Users/michaelahern/pgml-venv';

-- Option B : par session (test ponctuel)
SET pgml.venv = '/Users/michaelahern/pgml-venv';
```

### 3. Installer l'extension dans la base

```sql
\c finances
CREATE EXTENSION IF NOT EXISTS pgml CASCADE;
SELECT pgml.version();  -- doit retourner '2.10.9'
```

`CASCADE` ramène les dépendances (`plpython3u`, `vector`, etc.) si absentes.

### 4. Smoke test minimum

```sql
-- Vérifier que les bindings Python répondent (finding §4 : joblib disable auto-géré)
SELECT pgml.embed(
  'sentence-transformers/all-MiniLM-L6-v2',
  'test embedding finances'
);
-- Doit retourner un vecteur 384D
```

Si le premier appel échoue : voir §4 (joblib) et §11 (restart sans pipe stdout orphelin)
dans `BUILD-MACOS-NOTES.md`.

## Matrice des capacités (build locale, mai 2026)

| Module pgml                                        | Statut     | Notes                                                                                                                                                                                                  |
| -------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `pgml.embed`                                       | ✅         | sentence-transformers, BGE, Qwen3, multi-modèles HF                                                                                                                                                    |
| `embed-local-bge-small`                            | ✅         | BGE-small-en-v1.5 embedded 384D via `pgml.embed_local_passage/query`, offline sans download HF                                                                                                         |
| `pgml.chunk`                                       | ✅         | recursive, sentence, token splitters                                                                                                                                                                   |
| `pgml.rank`                                        | ✅         | cross-encoder reranking (validé §13 RAG end-to-end)                                                                                                                                                    |
| `pgml.transform`                                   | ✅         | HF pipelines : zero-shot, sentiment, summarization, traduction, NER                                                                                                                                    |
| `pgml.train` (sklearn)                             | ✅ partiel | linear, NB, kNN, xgboost, RF, kmeans                                                                                                                                                                   |
| `pgml.train` cluster                               | ✅         | kmeans + 3 alternatives online (patch §14)                                                                                                                                                             |
| `pgml.train` MLP (3 familles)                      | ✅         | validé runtime 2026-05-29 (mlp/rust_mlp/mlx_mlp, voir pgml-algorithms-catalog)                                                                                                                         |
| `pgml.train` DBSCAN                                | ⚠️         | clustering.sql:35-42 commenté upstream, à valider                                                                                                                                                      |
| `pgml.predict`                                     | ✅         | cold session unwrap patché 2026-05-05 (§12, EXPL-008)                                                                                                                                                  |
| `pgml.snapshot`                                    | ✅         | reproductibilité datasets (W2 cours MIA 5100)                                                                                                                                                          |
| `pgml.decompose`                                   | ⚠️         | PCA OK (§16 smoke 2026-05-06, cumul_var 0.97), 3 caveats A1 documentés                                                                                                                                 |
| `pgml.deploy`                                      | ✅         | lifecycle modèle (jamais smoké explicit, cible W11)                                                                                                                                                    |
| `pgml.tune` text-classification                    | ✅         | PATCHÉ 2026-05-06 (§9 EXPL-006, cascade 6 bugs : model.rs:164 + transformers.py:1235/:1427/:1418-1422 + doc class_column + workaround pgml.logs CREATE TABLE). Smoke distilbert+sst2 → f1=0.870, 39.8s |
| `pgml.tune` text-pair-classification, conversation | ⚠️         | sites SFTTrainer transformers.py:1057, :1629-1630 NON patchés (out of scope EXPL-006) — mêmes bugs structurels probables, cycle dédié futur                                                            |

Findings complets : `~/postgresml-build/pgml-extension/BUILD-MACOS-NOTES.md` §1-§17.

## Surface SQL (145 fonctions installées ; 17 documentées ci-dessous + couche MLX native)

Surface ML/NLP standard documentée ci-dessous. La couche d'inférence MLX/LLM native du fork (`llm_mlx`, `embed_mlx`, `rerank_mlx`, `audio_mlx`, `vlm_mlx`, `tune_mlx`, `fuse_mlx_adapter`, `hf_pull`) est exposée + installée mais **smoke runtime PENDING** — voir `pgml-mlx-native.md` (projet `postgresml-build/`). Exception validée : embedded local BGE-small expose `pgml.embed_local_passage(text)` / `pgml.embed_local_query(text)` → `public.vector(384)` ; il n'existe pas de `pgml.embed_local(...)` générique.

| Fonction                                                                                            | Variantes | Rôle                                                                                                                           | Rule locale détaillée |
| --------------------------------------------------------------------------------------------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------ | --------------------- |
| `pgml.train(project_name, task, relation_name, y_column_name, algorithm, hyperparams, search, ...)` | 1         | Pipeline ML supervised + clustering + decomposition (15 args)                                                                  | `pgml-train.md`       |
| `pgml.train_joint(project_name, task, relation_name, y_column_name TEXT[], ...)`                    | 1         | Multi-target regression (Python-only)                                                                                          | `pgml-train.md`       |
| `pgml.predict(project_name OR model_id, features)`                                                  | 9         | Inférence (REAL/DOUBLE/INT/BOOL[] + RECORD)                                                                                    | `pgml-predict.md`     |
| `pgml.predict_proba(project_name OR model_id, features)`                                            | 2         | Probabilités (classification only)                                                                                             | `pgml-predict.md`     |
| `pgml.predict_joint(project_name OR model_id, features)`                                            | 2         | Multi-target predict (regression only)                                                                                         | `pgml-predict.md`     |
| `pgml.predict_batch(project_name OR model_id, features)`                                            | 2         | Batch sérialisé                                                                                                                | `pgml-predict.md`     |
| `pgml.deploy(model_id BIGINT)` ou `pgml.deploy(project_name, strategy, algorithm)`                  | 2         | Promotion modèle (4 stratégies)                                                                                                | `pgml-deploy.md`      |
| `pgml.embed(transformer, text OR text[], kwargs)`                                                   | 2         | Embeddings sentence-transformers/BGE/E5/Qwen3                                                                                  | `pgml-embed.md`       |
| `pgml.embed_local_passage(text)` / `pgml.embed_local_query(text)`                                   | 2         | Embeddings embedded BGE-small-en-v1.5 384D offline/air-gapped                                                                  | `pgml-embed.md`       |
| `pgml.chunk(splitter, text, kwargs)`                                                                | 1         | Text splitting LangChain (7 splitters)                                                                                         | `pgml-chunk.md`       |
| `pgml.rank(transformer, query, documents[], kwargs)`                                                | 1         | Cross-encoder reranking (BGE/MiniLM/mxbai)                                                                                     | `pgml-rank.md`        |
| `pgml.transform(task, args, inputs, cache)`                                                         | 4         | HF NLP pipelines (zero-shot, NER, sentiment, fill-mask, etc.)                                                                  | `pgml-transform.md`   |
| `pgml.transform_stream(task, args, input/inputs, cache)`                                            | 4         | Streaming token-by-token (text-generation/conversational)                                                                      | `pgml-transform.md`   |
| `pgml.generate(project_name, inputs, config)`                                                       | 2         | Génération via projet déployé (whitelist bypass)                                                                               | `pgml-transform.md`   |
| `pgml.tune(project_name, task, relation_name, model_name, hyperparams, ...)`                        | 1         | Fine-tuning HF transformers (8 tasks) — ✅ text-classification PATCHÉ §9 EXPL-006 ; ⚠️ text-pair + conversation SFT non smokés | `pgml-tune.md`        |
| `pgml.decompose(project_name, vector)`                                                              | 1         | Application PCA déployé sur vecteur                                                                                            | `pgml-decompose.md`   |
| `pgml.snapshot(relation_name, y_column_name)`                                                       | 1         | Snapshot dataset (reproductibilité W2)                                                                                         | `pgml-train.md`       |
| `pgml.load_dataset(name)`                                                                           | 1         | Charge datasets canoniques (iris, diabetes, digits, linnerud, ...)                                                             | `pgml-train.md`       |

Snippet embedded local offline :

```sql
SELECT vector_dims(pgml.embed_local_passage('document clinique')) AS passage_dims,
       vector_dims(pgml.embed_local_query('question clinique')) AS query_dims;
```

## Catalogue algorithmes — `pgml.train`

51 variantes dans l'enum `Algorithm` (Rust source de vérité : `src/orm/algorithm.rs`). Tableau complet avec runtime effectif + binding cible : voir `pgml-algorithms-catalog.md`.

### Supervised (regression / classification)

| Famille                 | Algorithmes (suffixes `_regression` / `_classification`)                                                                                                                                                                                                                                                                                                                                                               | Runtime défaut                                          |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| **Linéaires sklearn**   | `linear`, `ridge`, `lasso` (reg only), `elastic_net` (reg only), `least_angle` (reg only), `lasso_least_angle` (reg only), `orthogonal_matching_pursuit` (reg only), `bayesian_ridge` (reg only), `automatic_relevance_determination` (reg only), `stochastic_gradient_descent`, `perceptron` (cls only), `passive_aggressive`, `ransac` (reg only), `theil_sen` (reg only), `huber` (reg only), `quantile` (reg only) | Python (sauf `linear` regression → Rust via linfa)      |
| **SVM**                 | `svm`, `nu_svm`, `linear_svm`                                                                                                                                                                                                                                                                                                                                                                                          | Python (override Rust via `runtime=>'rust'` pour `svm`) |
| **Kernel**              | `kernel_ridge` (reg only), `gaussian_process`                                                                                                                                                                                                                                                                                                                                                                          | Python                                                  |
| **Ensemble**            | `random_forest`, `extra_trees`, `bagging`, `ada_boost`, `gradient_boosting_trees`, `hist_gradient_boosting`                                                                                                                                                                                                                                                                                                            | Python                                                  |
| **Boosting Rust natif** | `xgboost`, `xgboost_random_forest`, `lightgbm`                                                                                                                                                                                                                                                                                                                                                                         | **Rust** (binding C++/C)                                |
| **Boosting Python**     | `catboost`                                                                                                                                                                                                                                                                                                                                                                                                             | Python (wheel 1.2.10)                                   |
| **kNN**                 | `knn`                                                                                                                                                                                                                                                                                                                                                                                                                  | Python (override Rust via smartcore)                    |

### Clustering (`task=>'cluster'` ou `'clustering'`)

5 algos online routés à `model.rs:540-547`. Métrique : `silhouette`.

| Algorithme                                                                            | Hyperparam principal | Statut local                                               |
| ------------------------------------------------------------------------------------- | -------------------- | ---------------------------------------------------------- |
| `kmeans`                                                                              | `n_clusters`         | ✅ §14 silhouette ~0.59                                    |
| `mini_batch_kmeans`                                                                   | `n_clusters`         | ✅ §14                                                     |
| `affinity_propagation`                                                                | `damping`            | ✅ §14                                                     |
| `birch`                                                                               | `n_clusters`         | ✅ §14                                                     |
| `mean_shift`                                                                          | `bandwidth`          | ⚠️ déclaré non smoké récemment                             |
| `dbscan`, `optics`, `spectral`, `spectral_bi`, `spectral_co`, `feature_agglomeration` | —                    | ❌ NON SUPPORTÉ upstream (`clustering.sql:35-42` commenté) |

### Decomposition (`task=>'decomposition'`)

1 algo. Métrique : `cumulative_explained_variance`.

| Algorithme | Hyperparam principal | Statut local                                          |
| ---------- | -------------------- | ----------------------------------------------------- |
| `pca`      | `n_components`       | ✅ smoke §16 2026-05-06 cumul_var 0.97 (3 caveats A1) |

## Splitters `pgml.chunk` (7 LangChain)

| Splitter              | Backend LangChain                | Use case                                                    |
| --------------------- | -------------------------------- | ----------------------------------------------------------- |
| `character`           | `CharacterTextSplitter`          | Découpe sur séparateur fixe                                 |
| `recursive_character` | `RecursiveCharacterTextSplitter` | **Recommandé RAG** (split hiérarchique `\n\n` → `\n` → ` `) |
| `markdown`            | `MarkdownTextSplitter`           | Préserve structure markdown                                 |
| `latex`               | `LatexTextSplitter`              | Préserve structure LaTeX                                    |
| `python`              | `PythonCodeTextSplitter`         | Préserve structure Python (def/class)                       |
| `nltk`                | `NLTKTextSplitter`               | Tokens NLTK (requiert `nltk.download('punkt')`)             |
| `spacy`               | `SpacyTextSplitter`              | Tokens spaCy                                                |

## Tasks `pgml.transform` (HF NLP)

11 variantes SQL combinant : `transform` (4) × `transform_stream` (4) × `generate` (2) + signatures JSONB/string. Détail surface `pgml-transform.md`.

Tasks HF principales validées :

- `text-classification` (BERT, RoBERTa)
- `zero-shot-classification` (BART, DeBERTa)
- `token-classification` / NER
- `summarization` (BART, T5, Pegasus) — patch §5 manuel
- `translation` (`translation_xx_to_yy`) — patch §5 manuel
- `question-answering` — patch §5 manuel
- `text-generation` (GPT-2, Llama, Mistral) + streaming
- `conversational` (chat history JSONB)
- `fill-mask`
- `image-classification` / `feature-extraction`

⚠️ Whitelist HF appliquée via GUC `pgml.huggingface_whitelist` (sauf `pgml.generate` qui bypass).

## Stratégies `pgml.deploy` (4)

| Stratégie                                | Code path                                              | Use case                                                  |
| ---------------------------------------- | ------------------------------------------------------ | --------------------------------------------------------- |
| `new_score`                              | Auto post-train si métriques meilleures (`api.rs:319`) | Déploiement automatique (default `automatic_deploy=true`) |
| `best_score`                             | ORDER BY métrique cible DESC/ASC selon task            | Promouvoir le meilleur modèle historique                  |
| `most_recent`                            | ORDER BY `created_at` DESC                             | Workaround §12 cold predict (warm cache)                  |
| `rollback`                               | JOIN deployments + exclut current                      | Revenir au modèle déployé précédent                       |
| `specific` (via `pgml.deploy(model_id)`) | Direct par id                                          | Promotion ciblée                                          |

Métriques cibles par task : `r2` (regression), `f1` (classification), `silhouette` (clustering), `cumulative_explained_variance` (decomposition), `bleu` (translation/conversation), `perplexity` (text-generation/text2text).

## Mapping cours MIA 5100 (W2-W11)

Alignement séquence pédagogique → capacités pgml. Source : `pgml-algorithms-catalog.md` <mapping_cours_uottawa> + `.claude/CLAUDE.md` projet `<coverage_concepts>`.

| Sem   | Concept cours               | Capacités pgml                                                                  | Statut local                                                             |
| ----- | --------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| W2    | ML Workflow + Snapshot      | `pgml.snapshot` + `pgml.train(linear)` baseline                                 | ✅                                                                       |
| W3    | Feature Engineering + PCA   | `pgml.train(preprocess=>...)` + `pgml.decompose` (PCA)                          | ⚠️ A1 deadline 2026-05-19                                                |
| W4    | Parametric / Non-parametric | `linear`, `bayesian_ridge`, `knn`, MLP (3 familles mlp/rust_mlp/mlx_mlp)        | ✅ MLP validé runtime 2026-05-29 (f1 cls 0.87-0.95)                      |
| W5    | Unsupervised Learning       | `kmeans`, `birch`, `mini_batch_kmeans`, `affinity_propagation`, DBSCAN          | ✅ 4 algos online ; ❌ DBSCAN                                            |
| W6    | Tuning + Ensemble           | `random_forest`, `gradient_boosting_trees`, `xgboost`, `lightgbm` + `pgml.tune` | ✅ ensemble + tune text-classif PATCHÉ §9 EXPL-006 (2026-05-06 f1=0.870) |
| W8-W9 | Deep Learning               | `pgml.transform` HF backend (CNN/RNN/LSTM via models HF)                        | ✅                                                                       |
| W10   | Text Analytics (RAG)        | `pgml.embed` + `pgml.chunk` + `pgml.rank`                                       | ✅ §13 RAG end-to-end                                                    |
| W11   | Model Deployment            | `pgml.deploy` lifecycle + bootstrap multi-cloud                                 | ⚠️ jamais smoké explicit                                                 |

<huggingface_auth>

## Authentification Hugging Face

`pgml.embed`, `pgml.transform`, `pgml.transform_stream`, `pgml.rank` et `pgml.tune`
téléchargent les modèles depuis le Hugging Face Hub via `huggingface_hub` (Python).
Les modèles **publics** marchent sans token. Les modèles **gated** (licence à accepter
sur huggingface.co — Llama 3.x, Gemma 2/3, MedGemma, plusieurs CLIP) exigent un token
HF résolvable au moment du `from_pretrained`.

### (a) Mécanisme natif huggingface_hub

`huggingface_hub` (vérifié `1.13.0` dans `/Users/michaelahern/pgml-venv`, `python -c "import huggingface_hub; print(huggingface_hub.__version__)"` 2026-05-06) résout le token dans cet ordre de précédence :

1. Variable d'env **`HF_TOKEN`** (canonique).
2. Variable d'env **`HUGGING_FACE_HUB_TOKEN`** (alias legacy, encore lu).
3. Fichier cache **`$HF_HOME/token`** (default `~/.cache/huggingface/token`),
   créé par `huggingface-cli login`. Constante exposée :
   `from huggingface_hub.constants import HF_TOKEN_PATH` → `/Users/michaelahern/.cache/huggingface/token`.
4. Fichier `stored_tokens` (multi-token alias, `huggingface_hub` 1.x) — utilisé seulement
   via `HfApi(token=<alias>)`. Pas dans la chaîne implicite par défaut.

Doc officielle : <https://huggingface.co/docs/huggingface_hub/main/en/package_reference/login>
(consultée 2026-05-06). Aucune GUC pgml n'est requise — `transformers.py` délègue 100% à
`huggingface_hub`. Evidence côté binding pgml :
`pgml-extension/src/bindings/transformers/transformers.py:1-22` injecte uniquement
les env vars `JOBLIB_*`, `TOKENIZERS_*`, `HF_HUB_DISABLE_PROGRESS_BARS`, `TQDM_DISABLE`,
`DATASETS_VERBOSITY` (findings §4 + §6) — **aucune injection `HF_TOKEN`**. Quand le
chargeur `SentenceTransformer(...)` ou `AutoTokenizer.from_pretrained(...)` s'exécute,
`huggingface_hub` résout via la chaîne 1→3 ci-dessus.

### (b) État Mac local (validé 2026-05-06)

| Élément                              | État                                                                                                                                                                                                                                                                                                                                                         |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Token cache                          | `~/.cache/huggingface/token` présent (37 bytes, login 2026-03-26) — valeur **REDACTED** (`hf_***...`)                                                                                                                                                                                                                                                        |
| `stored_tokens`                      | `~/.cache/huggingface/stored_tokens` présent (64 bytes, multi-token alias support `huggingface_hub` 1.x)                                                                                                                                                                                                                                                     |
| Cache size                           | 41 GB à `~/.cache/huggingface/` (hub + datasets + xet + modules)                                                                                                                                                                                                                                                                                             |
| Login user                           | `huggingface-cli login` exécuté côté user `michaelahern` (cache user, pas root, pas `_postgres`)                                                                                                                                                                                                                                                             |
| `HF_HOME`                            | **NON set** dans `~/Library/LaunchAgents/com.michaelahern.postgresql@17.plist` (seuls `PATH` et `LANG` y sont propagés). PG postmaster résout le cache via le **default `~/.cache/huggingface/` du HOME du user qui a chargé le launchd plist** — soit `michaelahern`. Vérifié `cat ~/Library/LaunchAgents/com.michaelahern.postgresql@17.plist` 2026-05-06. |
| `pgml.huggingface_whitelist`         | **vide** (`SHOW pgml.huggingface_whitelist;` → string vide) → tous modèles autorisés côté SQL actuellement                                                                                                                                                                                                                                                   |
| `pgml.huggingface_trust_remote_code` | `off` (default)                                                                                                                                                                                                                                                                                                                                              |
| Comportement implicite               | `pgml.embed('sentence-transformers/...', ...)` (public) marche sans token. Pour gated (Gemma 3, Llama 3.2) : `huggingface_hub` 1.13.0 lit `~/.cache/huggingface/token` automatiquement → l'auth fonctionne sans var d'env tant que PG tourne sous le user qui a fait `huggingface-cli login`.                                                                |
| Limite macOS LaunchAgent             | Si Michael relance PG sous un autre user Unix (ex: `sudo -u _postgres pg_ctl start`), le token cache `~/.cache/huggingface/token` du user `michaelahern` n'est PAS lu (HOME différent). Fallback : exporter `HF_TOKEN` dans le wrapper de start, OU ajouter `<key>HF_HOME</key><string>/Users/michaelahern/.cache/huggingface</string>` au plist.            |

### (c) Procédure VPS reproductible

Sur un VPS (Ubuntu 24.04, GCP/AWS/Azure) où PG tourne sous l'utilisateur système
`postgres`, il faut **soit** créer le cache pour cet utilisateur, **soit** injecter
`HF_TOKEN` dans l'environnement systemd. Préférer la 2ᵉ option (token rotatable
sans toucher au home dir).

**Option C.1 — systemd unit (recommandé prod) :**

```ini
# /etc/systemd/system/postgresql@17-main.service.d/override.conf
[Service]
Environment="HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
Environment="HF_HOME=/var/lib/postgresql/.cache/huggingface"
```

```bash
sudo systemctl daemon-reload
sudo systemctl restart postgresql@17-main
```

**Option C.2 — wrapper shell (dev/test) :**

```bash
# /usr/local/bin/start-pg-with-hf.sh
#!/usr/bin/env bash
set -euo pipefail
export HF_TOKEN="hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export HF_HOME="/var/lib/postgresql/.cache/huggingface"
exec /usr/lib/postgresql/17/bin/pg_ctl -D /var/lib/postgresql/17/main start
```

**Option C.3 — login sous l'utilisateur PG (uniquement si home dir disponible) :**

```bash
sudo -u postgres -H bash -lc 'huggingface-cli login --token $HF_TOKEN'
# Crée /var/lib/postgresql/.cache/huggingface/token
```

**Option C.4 — launchd plist (macOS, pattern Michael) :**

Pour Mac où PG tourne via `~/Library/LaunchAgents/com.<user>.postgresql@17.plist`, ajouter
les clés `HF_HOME` (et optionnellement `HF_TOKEN`) au dict `EnvironmentVariables`
existant :

```xml
<key>EnvironmentVariables</key>
<dict>
    <key>PATH</key>
    <string>/opt/homebrew/opt/postgresql@17/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
    <key>LANG</key>
    <string>en_US.UTF-8</string>
    <key>HF_HOME</key>
    <string>/Users/michaelahern/.cache/huggingface</string>
    <!-- Optionnel : sinon résolu via $HF_HOME/token (cache) -->
    <!-- <key>HF_TOKEN</key>
         <string>hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx</string> -->
</dict>
```

```bash
# Recharger le plist (procédure stricte launchctl macOS)
launchctl bootout gui/$(id -u)/com.michaelahern.postgresql@17 2>/dev/null || true
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.michaelahern.postgresql@17.plist
launchctl kickstart -k gui/$(id -u)/com.michaelahern.postgresql@17
```

⚠ État actuel Mac Michael (2026-05-06) : le plist **N'A PAS** `HF_HOME` ni `HF_TOKEN` —
ça marche pareil parce que `huggingface_hub` 1.13.0 default `~/.cache/huggingface/`
résolu via le HOME du user qui charge le LaunchAgent. Mais ajouter `HF_HOME` explicite
est plus robuste si on change de user d'exécution.

**Sécurité minimale** : `chmod 600` sur le fichier `override.conf` ou wrapper ou plist
(`chmod 600 ~/Library/LaunchAgents/com.michaelahern.postgresql@17.plist` après ajout du
token), ne JAMAIS commiter le plist contenant un `HF_TOKEN` en clair (pour Michael : le
plist est non versionné, mais à vérifier si un futur dotfiles repo l'inclut). Rotation
manuelle quand un membre de l'équipe quitte. Pour rotation chiffrée at-rest TGV-grade :
voir Option B reportée (GUC native pgml.huggingface_token chiffrée via pgsodium —
task `PGML-MEM5120-001` voie 1, hors scope de cette rule).

### (d) Cas d'erreur lisibles

| Symptôme côté SQL                                                                                   | Cause                                                                                                                                                           |
| --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `OSError: You are trying to access a gated repo. Make sure to request access ...`                   | Modèle gated mais licence non acceptée sur huggingface.co (`Authorization: Bearer` 403). Action : ouvrir la page HF du modèle et cliquer "Acknowledge license". |
| `huggingface_hub.errors.GatedRepoError: ... 401 Client Error`                                       | Token absent OU expiré OU mauvais `HF_HOME`. Action : `cat $HF_HOME/token` ou `echo $HF_TOKEN` dans l'env du process PG (`ps eww $(pgrep -f "postgres -D")`).   |
| `requests.exceptions.HTTPError: 401 Client Error: Unauthorized for url: https://huggingface.co/...` | Token revoke côté HF. Action : régénérer sur https://huggingface.co/settings/tokens et re-login.                                                                |
| Pas d'erreur, mais SELECT bloque indéfiniment                                                       | Download en cours (modèle non caché). Vérifier `ls -la ~/.cache/huggingface/hub/` — un dossier `models--<org>--<model>/blobs/` croît.                           |

**Debug snippet psql** :

```sql
-- Voir les messages stderr Python (download progress, GatedRepoError trace)
SET client_min_messages TO debug1;
SELECT pgml.transform(
    task    => '{"task": "text-generation", "model": "google/gemma-3-270m"}'::JSONB,
    inputs  => ARRAY['Hello'],
    args    => '{"max_new_tokens": 8}'::JSONB
);
```

### (e) Interaction avec `pgml.huggingface_whitelist`

Whitelist et auth sont **orthogonales** : la whitelist autorise/bloque l'**id du modèle**
au niveau pgml (sécurité interne, GUC `pgml.huggingface_whitelist`), l'auth gère
l'**accès au binaire HF** (côté hub HF, token user). Les 4 combinaisons :

| Whitelist                                   | Auth                         | Comportement                                                      | Cas d'usage                              |
| ------------------------------------------- | ---------------------------- | ----------------------------------------------------------------- | ---------------------------------------- |
| OK (modèle listé OU vide)                   | OK (public ou gated+licence) | ✅ Marche                                                         | Prod normale                             |
| OK                                          | KO (gated, pas de token)     | ❌ `GatedRepoError` côté Python                                   | Token mal configuré                      |
| KO (modèle absent d'une whitelist non-vide) | OK                           | ❌ `bail!("model X is not whitelisted")` côté Rust avant download | Sécurité interne (pas de fuite via pgml) |
| KO                                          | KO                           | ❌ Whitelist refuse en premier (Rust < Python)                    | Sécurité défense en profondeur           |

Note : `pgml.embed` et `pgml.rank` ne passent **PAS** par `whitelist::verify_task`
(`pgml-extension/src/bindings/transformers/whitelist.rs:11-37`), seuls les variants
`pgml.transform` et `pgml.transform_stream` font le check. `pgml.generate` bypass
aussi (project déjà déployé = whitelist vérifiée à `train` time). Implication : un
modèle gated en `pgml.embed` ne peut pas être bloqué par whitelist côté pgml — l'auth
HF est la seule défense en profondeur côté embeddings.

### (f) Snippet SQL complet — modèle gated léger

Exemple avec `google/gemma-3-270m` (270M params, gated, ~270 MB download cold) :

```sql
\c pgml_test

-- 1. Whitelister le modèle (sinon erreur Rust avant download)
SET pgml.huggingface_whitelist = 'google/gemma-3-270m';

-- 2. Smoke text-generation (download cold ~30-60s, warm <2s)
SELECT pgml.transform(
    task    => '{"task": "text-generation", "model": "google/gemma-3-270m"}'::JSONB,
    inputs  => ARRAY['The capital of France is'],
    args    => '{"max_new_tokens": 16, "do_sample": false}'::JSONB
);
-- Attendu : [{"generated_text": "The capital of France is Paris..."}] — preuve que l'auth HF
-- a fonctionné implicitement via cache user (~/.cache/huggingface/token).

-- 3. Vérifier que le download est arrivé
\! ls -la ~/.cache/huggingface/hub/ | grep gemma-3-270m
```

</huggingface_auth>

## Cas d'usage typiques (snippets SQL)

### Embeddings + recherche sémantique (combine avec pgvector)

```sql
ALTER TABLE finances.transactions
  ADD COLUMN description_emb vector(384);

UPDATE finances.transactions
SET description_emb = pgml.embed(
  'sentence-transformers/all-MiniLM-L6-v2',
  description
)::vector;

CREATE INDEX ON finances.transactions
  USING hnsw (description_emb vector_cosine_ops);

-- Recherche top-5 transactions similaires à une requête
SELECT id, description, description_emb <=> pgml.embed(
  'sentence-transformers/all-MiniLM-L6-v2',
  'paiement assurance auto'
)::vector AS distance
FROM finances.transactions
ORDER BY distance ASC LIMIT 5;
```

### Classification ou régression (sklearn)

```sql
-- Snapshot du dataset (reproductible)
SELECT pgml.snapshot('finances.fraud_features', 'is_fraud');

-- Entraînement
SELECT * FROM pgml.train(
  project_name => 'fraud_detection',
  task         => 'classification',
  relation_name => 'finances.fraud_features',
  y_column_name => 'is_fraud',
  algorithm    => 'xgboost'
);

-- Prédiction inline
SELECT id, pgml.predict('fraud_detection', (amount, merchant_id, hour)) AS proba
FROM finances.transactions
WHERE date >= CURRENT_DATE - INTERVAL '7 days';
```

### Fine-tuning HF text-classification (§9 EXPL-006, validé 2026-05-06)

```sql
-- Pré-requis : pgml.logs table (Bug 6 install gap workaround si fresh DB)
CREATE TABLE IF NOT EXISTS pgml.logs (
    id SERIAL PRIMARY KEY,
    model_id BIGINT,
    project_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    logs JSONB
);

-- Whitelister le modèle HF (ou GUC global)
SET pgml.huggingface_whitelist = 'distilbert/distilbert-base-uncased';

-- Fine-tune sur table source (text TEXT, label TEXT)
SELECT pgml.tune(
    'sentiment_finetune',
    task          => 'text-classification',
    relation_name => 'finances.feedback_classified',  -- ou pgml.sst2_text canonique
    model_name    => 'distilbert/distilbert-base-uncased',
    hyperparams   => '{
        "dataset_args": {"class_column": "label", "text_column": "text"},
        "num_train_epochs": 1,
        "per_device_train_batch_size": 8,
        "per_device_eval_batch_size": 8,
        "learning_rate": 5e-5,
        "max_seq_length": 64
    }'::JSONB,
    test_size     => 0.2
);
-- Retour : (sentiment_finetune, text-classification, transformers, t)
-- Logs INFO : f1=X.XX, accuracy=X.XX, train_loss=X.XX, "Deploying model id: N"

-- Inférence sur le modèle fine-tuné déployé
SELECT pgml.predict('sentiment_finetune', 'I love this product!');
```

⚠ **Convention dataset_args** : `class_column` / `text_column` (PAS `class_column_name` style HF — convention upstream Rust).
⚠ **CPU forcé sur Apple Silicon** : Bug 5 §9 force `use_cpu=True` quand pas de CUDA. Sur VPS Linux GPU, training automatiquement CUDA.
⚠ **Tasks SFT non patchées** : `text-pair-classification`, `conversation` non smokées dans EXPL-006 — risque de cascade similaire à §9.

### NLP zero-shot via HF

```sql
SELECT pgml.transform(
  task    => 'zero-shot-classification',
  inputs  => ARRAY['Paiement Belair Assurance auto'],
  args    => '{"candidate_labels": ["assurance", "épicerie", "restaurant", "essence"]}'::JSONB
);
```

### RAG end-to-end (validé §13)

```sql
-- 1. Chunk
SELECT pgml.chunk('recursive', long_text, '{"chunk_size": 512}'::JSONB)
FROM finances.documents;

-- 2. Embed les chunks (voir snippet plus haut)
-- 3. Retrieve top-k via pgvector + HNSW
-- 4. Rerank
SELECT pgml.rank('mixedbread-ai/mxbai-rerank-xsmall-v1', query, ARRAY[chunk_text]);
```

## Désinstaller / Rollback dans une base

```sql
DROP EXTENSION pgml CASCADE;        -- retire pgml de la DB courante
ALTER DATABASE finances RESET pgml.venv;  -- nettoie la GUC

-- L'extension reste installée côté binaire PG ; pas de réinstallation nécessaire
-- pour réactiver dans une autre base.
```

## Cross-references

### Ressources cross-projet (utiles depuis n'importe quelle base)

| Ressource                  | Path                                                                  | Rôle                                                                                                                         |
| -------------------------- | --------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Skill plugin officiel      | `intellisoins-postgresml:postgresml`                                  | Référence détaillée API + Docker fallback                                                                                    |
| Skill catalogue DB         | `intellisoins-postgresql:local-databases-catalog`                     | 22 bases locales + connection strings                                                                                        |
| Matrice capacités          | `BUILD-MACOS-NOTES.md` §1-§17                                         | Capacités pgml OK/KO post-patches (healthcheck manuel)                                                                       |
| Build notes macOS          | `~/postgresml-build/pgml-extension/BUILD-MACOS-NOTES.md`              | 17 findings §1-§17, procédures restart/install                                                                               |
| Projet build               | `~/postgresml-build/`                                                 | Source de vérité fork + patches + autopilot                                                                                  |
| Workflow build (rule)      | `~/postgresml-build/.claude/rules/pgml-extension-build.md`            | pgrx fmt/clippy/install avant commit                                                                                         |
| Auth HF (cette rule)       | `<huggingface_auth>` ci-dessus                                        | Token HF, cache, VPS systemd/launchd, orthogonalité whitelist                                                                |
| Whitelist HF (rule projet) | `~/postgresml-build/.claude/rules/pgml-transform.md` `<whitelist_hf>` | GUC `pgml.huggingface_whitelist` + `pgml.huggingface_trust_remote_code` (config.rs:7-11), code path `whitelist::verify_task` |

### Rules locales détaillées (auto-chargées dans `~/postgresml-build/`)

11 rules locales `~/postgresml-build/.claude/rules/pgml-*.md`, auto-chargées via `paths:` quand un fichier source pgml correspondant est touché. Chacune contient surface SQL exhaustive, flow Rust→bindings, deps Python, findings macOS, smoke tests, extension points. **Hors du projet `postgresml-build/`, ces rules ne sont pas auto-chargées** — ouvrir manuellement si besoin du détail.

| Rule                         | Capacité couverte                                                                                                | Trigger paths                                                             |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| `pgml-algorithms-catalog.md` | 51 algos × runtime × binding (source de vérité unique)                                                           | bindings ML, `algorithm.rs`, `model.rs`                                   |
| `pgml-train.md`              | `pgml.train` / `pgml.train_joint` (15 args, hyperparam search, preprocess)                                       | `examples/*classification.sql`, `examples/regression.sql`, `algorithm.rs` |
| `pgml-predict.md`            | 9 variantes `pgml.predict` + `predict_proba` + `predict_joint` + `predict_batch` (finding §12 cold session)      | `examples/*classification.sql`, `examples/regression.sql`                 |
| `pgml-deploy.md`             | 4 stratégies `pgml.deploy` + auto-deploy post-train                                                              | `strategy.rs`, `project.rs`, `examples/*classification.sql`               |
| `pgml-cluster.md`            | `pgml.train(task=>'cluster')` 5 algos online + DBSCAN bloqué                                                     | `bindings/sklearn/**`, `examples/clustering.sql`, `task.rs`               |
| `pgml-decompose.md`          | `pgml.decompose` + `pgml.train(task=>'decomposition')` PCA W3                                                    | `bindings/sklearn/**`, `examples/decomposition.sql`                       |
| `pgml-tune.md`               | `pgml.tune` (8 tasks fine-tuning HF) — **text-classification PATCHÉ §9 EXPL-006 2026-05-06** ; SFT tasks pending | `bindings/transformers/**`, `examples/finetune.sql`                       |
| `pgml-transform.md`          | 11 variantes `pgml.transform` / `transform_stream` / `generate` + whitelist HF                                   | `bindings/transformers/**`, `whitelist.rs`, `examples/transformers.sql`   |
| `pgml-embed.md`              | 2 variantes `pgml.embed` (single + batch) + embedded local BGE-small passage/query                               | `bindings/transformers/**`, `examples/embedding.sql`                      |
| `pgml-chunk.md`              | `pgml.chunk` (7 splitters LangChain)                                                                             | `bindings/langchain/**`, `examples/chunking.sql`                          |
| `pgml-rank.md`               | `pgml.rank` cross-encoder reranking                                                                              | `bindings/transformers/**`                                                |

## Anti-patterns

- **Ne pas** créer pgml dans une base sans avoir d'abord configuré `pgml.venv` →
  premier appel Python échoue avec import torch obscur.
- **Ne pas** appeler `pgml.tune` task=>'text-pair-classification' ou 'conversation' (sites SFTTrainer transformers.py:1057, :1629-1630 non patchés ; mêmes bugs structurels que §9 probables). Text-classification ✅ supporté depuis EXPL-006 (2026-05-06).
- **Ne pas** oublier `CREATE TABLE IF NOT EXISTS pgml.logs (...)` après `CREATE EXTENSION pgml CASCADE` sur fresh DB (Bug 6 §9 install gap baseline upstream — workaround documenté dans `BUILD-MACOS-NOTES.md` §9).
- **Ne pas** utiliser convention HF `class_column_name` / `text_column_name` dans `pgml.tune` `dataset_args` — code Rust attend `class_column` / `text_column` (sans suffixe `_name`). Voir snippet fine-tuning ci-dessous.
- **MLP supporté depuis 2.10.9** (3 familles : `mlp_classification`/`mlp_regression` sklearn,
  `rust_mlp_*` Rust pur, `mlx_mlp_*` MLX) — validé runtime 2026-05-29. Voir `pgml-algorithms-catalog.md`.
- **Ne pas** restart PG via `brew services restart` si stdout est piped → finding §11
  (utiliser `pg_ctl -l logfile` explicit ou détacher le terminal).
- **Ne pas** commiter un `HF_TOKEN` en clair dans un launchd plist, systemd unit, wrapper
  shell ou Dockerfile versionné. Si le plist Mac est inclus dans un futur dotfiles repo,
  utiliser `EnvironmentFile` (systemd) ou un wrapper qui lit `cat /secure/hf_token`
  (chmod 600). Pour TGV : Option B chiffrée pgsodium (reportée).
- **Ne pas** confondre `pgml.huggingface_whitelist` (sécurité SQL côté Rust pgml, bloque
  les modèles non listés AVANT download — `whitelist.rs:11-37`) avec l'auth HF (token
  côté Python `huggingface_hub`). Les deux sont **orthogonales** : whitelist vide +
  modèle gated sans token = `GatedRepoError` Python ; whitelist non-vide sans le modèle =
  `bail!("not whitelisted")` Rust avant que Python soit invoqué.
- **Ne pas** assumer que `HF_HOME`/`HF_TOKEN` est propagé à PG sans vérifier le
  postmaster live : `ps eww $(pgrep -f "postgres -D /opt/homebrew/var/postgresql@17") |
tr ' ' '\n' | grep -E '^HF_'`. Sur Mac launchd, seuls les vars listées dans
  `EnvironmentVariables` du plist sont héritées — pas le shell login de l'utilisateur.
