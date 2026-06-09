---
paths:
  - "**/*.sql"
  - "**/pgvector*.json"
  - "**/scripts/*index*.py"
  - "**/scripts/*enrich*.py"
  - "**/scripts/*trigger*.py"
  - "**/scripts/audit_extensions*"
---

# Catalogue des Bases PostgreSQL Locales

Inventaire des 27 bases PostgreSQL Homebrew sur localhost:5432 (PostgreSQL 17.8).
Tailles verifiees: 2026-06-05. Row counts: 2026-04-02 (bases pre-existantes).

Connection: `psql -h localhost -U michaelahern -d <database>`
URI: `postgresql://michaelahern:@localhost:5432/<database>`

## Vue d'ensemble

| Base                           | Taille  | Schemas                                                                                     | Tables         | Vues | Rows totales      | Extensions notables                                                |
| ------------------------------ | ------- | ------------------------------------------------------------------------------------------- | -------------- | ---- | ----------------- | ------------------------------------------------------------------ |
| **claude_usage**               | 19 GB   | 1 (public)                                                                                  | 5              | 0    | ~2.9M             | socle 39 + pgml 2.10.8\*                                           |
| **medical**                    | 2074 MB | 6 (public, clinical, gmf, pharmacy, clinical_graph, ag_catalog)                             | 88             | 35   | ~160K             | socle 39 + age 1.7.0 + pgml 2.10.5\*                               |
| **pgml_test**                  | 539 MB  | ~22 (tests)                                                                                 | 21             | 3    | — (smoke test)    | pgml 2.10.9, vector 0.8.2, plpython3u, dblink                      |
| **emails**                     | 180 MB  | 1 (public)                                                                                  | 3              | 0    | ~5.5K             | socle 39 + age 1.7.0                                               |
| **finances**                   | 132 MB  | 2 (public, ag_catalog)                                                                      | 45             | 36   | ~9K               | socle 39 + age 1.7.0, pgml 2.10.5\*, pg_cron 1.6, vectorize 0.23.0 |
| **intellisoins-pubmed**        | 108 MB  | 1 (public)                                                                                  | 10             | 7    | ~290              | socle 39                                                           |
| **genealogy**                  | 86 MB   | 3 (public, family_tree, ag_catalog)                                                         | 8+4 AGE        | 3    | ~246              | socle 39 + age 1.7.0                                               |
| **intelligence_artificielle**  | 84 MB   | 8 (public, ai, pgml, paradedb, pdb, duckdb, pgmq, ag_catalog)                               | 9              | 1    | 4,199             | socle 39 + pgml 2.10.6\*                                           |
| **mia5100z_course**            | 57 MB   | 4                                                                                           | 71             | 6    | —                 | pgml 2.10.7\*, vector 0.8.2, plpython3u                            |
| **pgml_dashboard_development** | 46 MB   | 6                                                                                           | 44             | 3    | —                 | pgml 2.10.9, vector 0.8.2, plpython3u, dblink                      |
| **navig**                      | 44 MB   | 5 (public, raw, ref, anon, analytics)                                                       | 27 (dont 3 MV) | 10   | ~18K              | socle 39 (⚠ anon RETIRE)                                           |
| **facturation_gmf**            | 20 MB   | 8 (public, boost2_metrics, clinical, pharmacy, audit, audit_trail, test_boost2, ag_catalog) | ~90            | 42   | ~2K               | socle 39 + age 1.7.0                                               |
| **omnimed**                    | 17 MB   | 1 (public)                                                                                  | ~5             | 0    | ~527              | socle 39                                                           |
| **litellm**                    | 16 MB   | 1 (public)                                                                                  | 65             | 8    | ~28 (app LiteLLM) | vector 0.8.2, plpython3u                                           |
| **imessages**                  | 16 MB   | 1 (public)                                                                                  | 1              | 0    | 19,338            | socle 39                                                           |
| **teams**                      | 12 MB   | 1 (public)                                                                                  | 4              | 2    | ~293              | socle 39                                                           |
| **filesystem_db**              | 12 MB   | 1 (public)                                                                                  | 5              | 4    | 0 (vide)          | socle 39                                                           |
| **recettes_db**                | 12 MB   | 1 (public)                                                                                  | 6              | 0    | ~1.5K             | socle 39                                                           |
| **masterIA**                   | 11 MB   | 1 (public)                                                                                  | 1              | 0    | 5                 | socle 39                                                           |
| **cdp_phm_gmf**                | 11 MB   | 1 (public)                                                                                  | ~5             | 0    | ~10               | socle 39                                                           |
| **whisper_dictations**         | 11 MB   | 1 (public)                                                                                  | 1              | 0    | 49                | socle 39                                                           |
| **assurance**                  | 11 MB   | 1 (public)                                                                                  | 6              | 3    | ~65               | socle 39                                                           |
| **appsq**                      | 11 MB   | 1 (public)                                                                                  | 0              | 0    | 0                 | socle 39 + age 1.7.0                                               |
| **intellisoins_test**          | 10 MB   | 1 (public)                                                                                  | 32             | 0    | —                 | ltree, plpython3u, vector 0.8.2                                    |
| **mia5100z**                   | 9.3 MB  | 4                                                                                           | 6              | 6    | —                 | pgml 2.10.5\*, pg_search, vchord, http, vector 0.8.2               |
| **litellm_pgvector**           | 8 MB    | 1 (public)                                                                                  | 2              | 0    | —                 | vector 0.8.2, plpython3u                                           |
| **postgres**                   | 7.8 MB  | -                                                                                           | 0              | 0    | 0                 | vector 0.8.2, plpython3u                                           |

`*` = catalogue SQL pgml en retard sur la lib 2.10.9 (voir section PostgresML). « socle 39 » = 39 extensions communes (`template1`), detaillees en « Extensions par base ». ⚠ = drift extension valide 2026-06-05.

## Bases principales (avec donnees actives)

### medical (base clinique/pharmacie — la plus volumineuse)

Base principale pour les donnees cliniques, pharmacie, GMF et graphe Apache AGE.
**80,018 document_embeddings** (5,227 docs uniques) avec halfvec(1024) et HNSW cosine index.
Socle 39 ext. + age 1.7.0 (graphe clinical_graph) + pgml 2.10.5\*, pgvector 0.8.2, pg_stat_statements 1.11.

Schemas: `public`, `clinical`, `gmf`, `pharmacy`, `clinical_graph` (Apache AGE), `ag_catalog`.

Tables cles avec donnees:

- `public.document_embeddings` (80,018 rows) — chunks documents medicaux, halfvec(1024), ~2 GB
- `clinical_graph.INTERAGIT_AVEC` (39,511) — interactions medicamenteuses (AGE edge)
- `clinical_graph.DiagnosticCIM` (12,336) — diagnostics CIM-10 (AGE vertex)
- `clinical_graph.Produit` (11,423) — produits pharmaceutiques (AGE vertex)
- `gmf.patients` (3,323) — patients GMF Harricana
- `gmf.time_sheets` (77) — feuilles de temps pharmacien GMF (date, start/end_time, total_worked_minutes, description, location)
- `gmf.activities` (136) — activites cliniques pharmacien (grilles MSSS: optimisation_pharma, EPAP, provenance, type_patient)
- `gmf.interventions` (1) — interventions individuelles (code_ramq, type, duree, est_optimisation)
- `public.clinical_documents` (437) — documents cliniques avec embeddings vector
- `public.deprx_*` (7 tables) — systeme deprescription (patients, medications, ACB, Beers)
- `public.drugs` + drug_forms/ingredients/routes/statuses — BDPP Sante Canada
- `public.facebook_group_posts` (6) — posts scrapes du groupe FB "Pharmaciens et Pharmaciennes du Quebec (Membre OPQ)"
- `public.facebook_group_comments` (17) — commentaires associes aux posts FB
- `public.pharmacist_pain_points` (16) — pain points categorises (10 categories, 4 severites) extraits des commentaires

Vues market research: `v_pain_points_summary` (par categorie/severite), `v_comments_with_pain_points` (commentaires + classification).

Voir `~/.claude/plugins/intellisoins-plugins/intellisoins-postgresql/skills/local-databases-catalog/references/medical-schema.md` pour colonnes detaillees.

### claude_usage (pipeline fine-tuning Claude Code + cross-ref conversations)

5 tables, ~19 GB. **40 extensions installees** dont `vector` (pgvector 0.8.2), `pg_search` (ParadeDB BM25 0.22.5), `vchord` (0.0.0), `pg_trgm` (1.6), `fuzzystrmatch`, `pgml` (PostgresML 2.10.8 installee, catalogue SQL en retard sur lib 2.10.9). Ingest auto via LaunchAgent `com.intellisoins.claude-training-pipeline` (StartInterval 1800s) qui glob `~/.claude/projects/**/*.jsonl` → ingest+generate+export. Couvre tous les projets sur ce Mac (pas de filtre projet). Lag max ~30 min.

**Tables** :

- `messages` (~1.58M rows, 4,848 MB) — messages complets, **colonne `search_vector tsvector` (trigger BEFORE INSERT/UPDATE ponderee `role(A) || content_text(B) || thinking(C)`)** + indices GIN search_vector + GIN pg_trgm sur content_text
- `tool_calls` (~1.27M rows, 8,538 MB) — appels d'outils extraits
- `training_examples` (~51,7K rows, 1,102 MB) — exemples fine-tuning generes
- `sessions` (~17,5K rows, 20 MB) — sessions Claude Code, **colonnes `embedding vector(1024)` (Qwen3-Embedding-8B local `:8084` souverain) + `embedding_text` + `embedded_at`**. Index HNSW vector_cosine_ops.
- `export_formats` — formats d'export fine-tuning

**Helper SQL** : `find_related_sessions(query_text text, query_embedding vector(1024) DEFAULT NULL, max_results int DEFAULT 10, min_bm25_rank float DEFAULT 0.01, min_cosine_sim float DEFAULT 0.5)`. Cascade BM25 + pg_trgm + cosine HNSW, score combine `bm25*2 + cosine*1.5 + trgm*1`. Utilise par mini-audit pre-triage (Etape 0quater de `state-audit.md`).

**Souverainete** : embeddings via Qwen3-Embedding-8B local Mac (zero sortie machine, Loi 25 art.17 compatible). Aucune dependance reseau au-dela de localhost.

Source de truth : cette section. La fiche secondaire `secondary-databases.md` cross-ref ici.

### finances (gestion financiere personnelle/entreprise)

45 tables (43 public + 2 ag_catalog), 36 vues, 132 MB. Systeme complet de finances personnelles et d'entreprise.
Apache AGE 1.7.0 (graphe financier **reactive le 2026-06-05** ; `cypher()` operationnel, graphe relationnel a re-peupler). pgvector 0.8.2 pour documents classifies. pg_trgm 1.6, + pg_cron 1.6 et vectorize 0.23.0 (uniques a cette base).

Tables cles:

- `transactions` (5,036 rows) — 26 cols, 10 FK, 12 index (debit/credit, compte/fournisseur/categorie, owner, fiscal)
- `fournisseurs` (584) — vendor mapping avec normalized_name et category_id, self-ref parent
- `budget_categories` (214) — categories budgetaires, FK parent_categories (24 parents)
- `classified_documents` (1,296) — factures/releves OCR avec embedding vector(1024)
- `document_embeddings` (1,236) — documents financiers indexes halfvec(1024), HNSW
- `category_tags` (96) — pivot budget_categories → fiscal_category + % deductible
- `declaration_lines` (56) — lignes declarations fiscales T2125/TP-80 2024-2025
- `deductions_personnelles` (31) — deductions T1/TP-1 avec taux fed/QC, lignes, plafonds

Tables placements (6 comptes, 47 positions):

- `comptes_placement` (6) — 3 Disnat (Michael) + 2 Assante CI (Marie-Eve) + 1 REEE familial
- `positions_placement` (47) — 31 Disnat + 13 Assante + 3 REEE, UNIQUE(compte+symbole)
- `evaluations_position` (47), `evaluations_portefeuille` (6) — snapshots valeur marche

Tables stock analysis:

- `stock_fundamentals` (~27/jour) — fondamentaux yfinance + 6 methodes valeur intrinseque
- `stock_dividends` (0), `stock_financial_statements` (0) — historique dividendes et etats financiers

Tables bilan:

- `actifs_non_financiers` (3) — immobilier (281,500$ eval. mun. Amos), vehicules (Odyssey 2022, RAV4 2011)
- `produits_financement` (4) — hypotheque, marge hypo, marge perso, pret hypo (Desjardins, ~213K$)

Vues analytiques (36): `v_transactions_enriched`, `v_valeur_nette` (actifs financiers + non-financiers - passifs), `v_sommaire_fiscal`, `v_portrait_actifs`, `v_positions_enriched`, `v_stock_valuation`, `v_stock_screening`, etc.

Voir `~/.claude/plugins/intellisoins-plugins/intellisoins-postgresql/skills/local-databases-catalog/references/finances-schema.md` pour colonnes detaillees.

### emails (archive courriels)

3 tables, 331 MB. Archive de courriels Apple Mail.app avec embeddings et contacts.

- `email_archive` (5,514 rows) — message_id, thread_id, from/to/cc, subject, body, embedding vector(dim), labels
- `contacts` (1,051) — display_name, type, org_name, domain, phone, address
- `contact_emails` (782) — email addresses liees aux contacts, avec msg_count

### facturation_gmf (facturation et metriques pharmacien GMF)

Renommee de `boost2_db` le 2026-03-27. Schema `medical_graph` supprime (miroir inutile de `medical.clinical_graph`).
Schemas: `public`, `boost2_metrics`, `clinical`, `pharmacy`, `audit`, `audit_trail`, `test_boost2`, `ag_catalog`.
La plupart des tables sont vides (template dev), **sauf les tables de suivi d'heures et activites**:

- `boost2_metrics.time_sheets` (80) — feuilles de temps pharmacien GMF (date, heures, description, location)
- `boost2_metrics.activities` (136) — activites cliniques (grilles MSSS)
- `boost2_metrics.patients` (1,297) — patients GMF avec codes vulnerabilite
- `public.activities` (133) — copie des activites

**Note desync**: Les donnees time_sheets existent en parallele dans `medical.gmf.time_sheets` (77 rows)
et `facturation_gmf.boost2_metrics.time_sheets` (80 rows). `facturation_gmf` contient les entrees les plus recentes.
Modules: patients, interventions, prescriptions, facturation, agents IA, conversations, documents, invoices.

Voir `~/.claude/plugins/intellisoins-plugins/intellisoins-postgresql/skills/local-databases-catalog/references/boost2-schema.md` pour colonnes detaillees.

### navig (projet NAVIG/Vitr.ai — trajectoires GMF)

27 tables (dont 3 materialized views), 10 vues, 44 MB. Socle 39 ext. **⚠ anon RETIRE** (valide 2026-06-05) : l'extension `anon` (jadis 3.0.13) n'est plus installee, le schema `anon` est vide — les tables `anon.fake_*` et fonctions `anon.age_bucket/to_season` decrites plus bas n'existent plus. A restaurer si l'anonymisation Loi 25 est requise.
Base dediee au projet NAVIG/Vitr.ai (trajectoires pharmacien GMF Amos).
5 schemas: `public`, `raw`, `ref`, `anon`, `analytics`.

Tables cles:

- `public.documents_gmf` (2,031 rows) — chunks documents GMF (OC, procedures, protocoles), halfvec(1024), FK source_medical_id vers medical
- `raw.patients` (20 rows) — donnees patient synthetiques (trajectoire_id, categorie, motif, statut, delai, FK professionnels)
- `public.professionnels` (15) — types professionnels GMF (MD, IPS, PHM, INF...)
- `public.tranches_age` (8) — tranches hybrides OMS (<65) + geriatrie (65+)
- `public.patients_anon` (vue) — vue anonymisee sans identifiants, avec bruit et generalisation
- `ref.defavorisation_inspq_2021` (13,805) — indice defavorisation par aire de diffusion (INSPQ)
- `ref.urgences_msss` (795) — visites urgences par installation/annee (MSSS)
- `ref.benchmarks_reperes_gmf` (23) — indicateurs qualite provinciaux (INESSS)
- `ref.profil_rls` (22) — profil populationnel RLS 812 Abitibi (Amos)
- `ref.v_tableau_bord_gmf_amos` (vue) — tableau de bord miroir Reperes GMF
- `analytics.urgences_enrichies` (575, MV) — urgences JOIN defavorisation par RSS, features ML
- `analytics.defavorisation_agregee` (280, MV) — defav multi-niveaux via GROUPING SETS (RSS/RLS/CLSC)
- `analytics.serie_temporelle_urgences` (575, MV) — series temporelles avec variation annuelle LAG
- `anon.*` (13 tables fake\_\*) — donnees fictives pour anonymisation (extension anon)

Fonctions custom: `anon.age_bucket(DATE)`, `anon.to_season(DATE)`.
(FDW PostgresML retire — voir section PostgresML ci-dessous pour migration vers fork Rust natif.)

### genealogy (arbre genealogique Ahern)

8 tables public + 4 tables AGE (family_tree), 3 vues, 9.6 MB.
Apache AGE 1.7.0 pour graphe familial. Socle 39 ext.
Schemas: `public`, `family_tree` (Apache AGE), `ag_catalog`.

Tables cles:

- `persons` (60 rows) — given_name, surname, maiden_name, gender, birth/death_date, familysearch_id, gramps_id, occupation, notes
- `families` (19) — partner1_id, partner2_id, marriage_date, marriage_place_id
- `children` (38) — family_id, person_id, relationship_type (biological/foster), birth_order
- `places` (25) — name, full_name, place_type, parent_id, ltree path, lat/lon

Graphe AGE (`family_tree`): Person (32 vertices), PARENT_OF (44 edges), SPOUSE_OF (8 edges).
Ancetre fondateur: **Henry Ahern** (LWT4-YN2), ne 1892 Boston, premier maire de Parent QC.

### assurance (comparaison polices auto/habitation)

6 tables, 3 vues, 8.1 MB. Comparaison Belair Direct (polices actives) vs La Personnelle (soumissions).

Tables cles:

- `polices` (4 rows) — assureur, type (habitation/auto), no_police/no_soumission, statut, primes
- `couvertures` (26 rows) — garanties/avenants par police: code_avenant, montant, franchise, prime
- `vehicules` (4 rows) — 2 vehicules x 2 assureurs
- `propriete` (1 row) — 931 Rue Des Sorbiers Amos

Polices actives: Belair Direct habitation KKE-CMTJ (1 853$/an), auto KKC-KVH2 (1 582$/an).
Soumissions: La Personnelle habitation UCK0Q0WM (1 230$/an + taxe), auto ECGW5MQV (1 013$/an + taxe).

### imessages (archive iMessages)

1 table, 13 MB. 19,338 messages (7,325 sent / 12,013 received), 332 contacts, 353 conversations.
Periode: jul 2024 — mars 2026. Source: extraction SQLite Apple Messages.

### whisper_dictations (transcriptions vocales Hammerspoon)

1 table. Pipeline automatique via Cmd+ç (et variantes).

- `transcriptions` (49 rows) — wav_path, transcription, language, active_app, hotkey, created_at
  Source: Hammerspoon init.lua → logTranscription() → psql INSERT async.

### teams (messages Microsoft Teams MSSS)

4 tables, 2 vues, 12 MB. Socle 39 ext. (pgvector 0.8.2, pg_trgm 1.6).
Messages Teams MSSS (`michael.ahern@ssss.gouv.qc.ca`), extraits via automatisation Chrome.

- `channels` (1) — team_name, channel_name, channel_type, last_synced_at
- `messages` (149) — author, author_role, content, message_ts, content_hash (SHA-256 dedup)
- `message_embeddings` (141) — halfvec(1024) HNSW, chunk_text, search_vector tsvector
- `sync_log` (2) — journal des sessions d'extraction

### intellisoins-pubmed (metriques business IntelliSoins)

10 tables, 7 vues, 8.5 MB. Google Ads analytics + tables pricing (vides).

- `ads_daily_metrics` (222 rows) — snapshots quotidiens (impressions, clicks, cost_cad, conversions)
- `ads_campaigns` (1) — Smart Campaign "IntelliSoins" (ID 22820387505), 2025-07-27 → 2026-03-31, REMOVED
- `ads_search_terms` (43) — termes de recherche

### recettes_db (recettes cuisine + epicerie)

6 tables. App de recettes avec catalogue produits epicerie et suivi d'achats.

- `Recipe` (95 rows) — title, url, source, author, ingredients, instructions, tags
- `Product` (416) — catalogue produits avec barcode UPC/EAN, brand, category
- `Purchase` (1,041) — historique achats (FK → Product), price, quantity, store, date

### Bases mineures

- **omnimed** (17 MB) — Prototype indexation documents Omnimed. `document_embeddings` (517), `content_categories` (10).
- **cdp_phm_gmf** (11 MB) — Prototype CDP pharmacien GMF. `document_embeddings` (10).
- **masterIA** (11 MB) — Base minimale prototype. `document_embeddings` (5).
- **intelligence_artificielle** (84 MB, active) — Bibliotheque de manuels ML/IA pour l'etude (MIA5100Z). `public.document_embeddings` (4,199 chunks de 1,805 PDF: Bishop, Elements of Deep Learning, etc. — Qwen3-0.6B halfvec 1024D + tsvector). Schema `ai` = pipeline RAG/generation/fine-tuning (amorce). Fonction **`recherche_ml(question)`** = RAG natif (embed :8084 + rerank :8085 via http, ~1.5 s). Stack: pgml 2.10.6\* (catalogue en retard sur lib 2.10.9), pg_search, pg_duckdb, vchord, pgmq. Voir rule projet `recherche-base-ia.md`. AGE retire.
- **appsq** (11 MB) — Congres APPSQ Expo Pharma 67 (15-16 mai 2026). Socle 39 ext. + age 1.7.0 (reactive 2026-06-05 ; pgvector 0.8.2). Vide (schema a creer).
- **filesystem_db** (12 MB) — Index systeme fichiers macOS. Vide.
- **postgres** (7.8 MB) — Base systeme par defaut. Vide.

### Bases ajoutees depuis 2026-04 (audit 2026-06-05)

- **pgml_test** (539 MB) — base smoke-test du fork pgrx (`~/postgresml-build/`). pgml 2.10.9, vector 0.8.2, plpython3u, dblink. ~22 schemas de test ephemeres, 21 tables.
- **pgml_dashboard_development** (46 MB) — base du dashboard PostgresML (dev). pgml 2.10.9, vector 0.8.2, plpython3u, dblink. 6 schemas, 44 tables.
- **mia5100z_course** (57 MB) — variante cours MIA5100Z (71 tables, 6 vues). pgml 2.10.7\*, vector 0.8.2.
- **mia5100z** (9.3 MB) — base cours MIA5100Z (6 tables). Stack RAG: pgml 2.10.5\*, pg_search 0.22.5, vchord, http, vector 0.8.2.
- **litellm** (16 MB) — base applicative du gateway LiteLLM local (65 tables, 8 vues ; migrations propres a l'app). pgvector 0.8.2. Ne pas y installer pgml.
- **litellm_pgvector** (8 MB) — store vectoriel LiteLLM RAG (2 tables). pgvector 0.8.2.
- **intellisoins_test** (10 MB) — base de test app IntelliSoins (32 tables). pgvector 0.8.2, ltree.

## Extensions par base

Valide 2026-06-05 via `pg_extension`. **19 bases partagent un socle commun de 39 extensions** (provisionne via `template1`) ; 8 bases sont minimales.

**Socle commun (39 ext)** :
`amcheck 1.4, bloom 1.0, btree_gin 1.3, btree_gist 1.7, citext 1.6, cube 1.5, dblink 1.2, earthdistance 1.2, file_fdw 1.0, fuzzystrmatch 1.2, hstore 1.8, http 1.7, hypopg 1.4.2, intarray 1.5, isn 1.2, lo 1.1, ltree 1.3, pageinspect 1.12, pg_buffercache 1.5, pg_duckdb 1.1.0, pg_prewarm 1.2, pg_search 0.22.5, pg_stat_statements 1.11, pg_trgm 1.6, pg_visibility 1.2, pg_walinspect 1.1, pgcrypto 1.3, pgmq 1.11.0, pgrowlocks 1.2, pgstattuple 1.5, plpython3u 1.0, postgres_fdw 1.1, seg 1.4, sslinfo 1.2, tablefunc 1.0, unaccent 1.1, uuid-ossp 1.1, vchord 0.0.0, vector 0.8.2`

**Socle pur (11)** : assurance, cdp_phm_gmf, filesystem_db, imessages, intellisoins-pubmed, masterIA, navig, omnimed, recettes_db, teams, whisper_dictations.

**Socle + extras (9)** :

| Base                      | Extras vs socle                                         |
| ------------------------- | ------------------------------------------------------- |
| medical                   | age 1.7.0, pgml 2.10.5\*                                |
| emails                    | age 1.7.0                                               |
| genealogy                 | age 1.7.0                                               |
| facturation_gmf           | age 1.7.0                                               |
| appsq                     | age 1.7.0                                               |
| claude_usage              | pgml 2.10.8\*                                           |
| intelligence_artificielle | pgml 2.10.6\*                                           |
| finances                  | age 1.7.0, pgml 2.10.5\*, pg_cron 1.6, vectorize 0.23.0 |

**Bases minimales (8, hors socle)** :

| Base                                  | Extensions                                                                                                                          |
| ------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| pgml_test, pgml_dashboard_development | dblink 1.2, pgml 2.10.9, plpython3u 1.0, vector 0.8.2                                                                               |
| mia5100z                              | fuzzystrmatch 1.2, http 1.7, pg_search 0.22.5, pg_trgm 1.6, pgml 2.10.5\*, plpython3u 1.0, unaccent 1.1, vchord 0.0.0, vector 0.8.2 |
| mia5100z_course                       | pgml 2.10.7\*, plpython3u 1.0, vector 0.8.2                                                                                         |
| intellisoins_test                     | ltree 1.3, plpython3u 1.0, vector 0.8.2                                                                                             |
| litellm, litellm_pgvector, postgres   | plpython3u 1.0, vector 0.8.2                                                                                                        |

`*` = catalogue pgml en retard sur lib 2.10.9 (voir section PostgresML).

**⚠ Drift extensions detecte (2026-06-05)** :

- **AGE** : v **1.7.0** (plus 1.6.0). **Reactivee le 2026-06-05** dans finances, facturation_gmf, appsq (schema `ag_catalog` vestige etait vide) → presente dans **6 bases** : medical, emails, genealogy, finances, facturation_gmf, appsq. `cypher()` reoperationnel ; graphes non re-peuples (etaient vides).
- **anon** : **retiree de navig** (schema `anon` vide). Plus aucune base ne l'a — les `anon.*` et `anon.age_bucket/to_season` decrits en section navig n'existent plus.
- **vector** : 0.8.2 partout (la rule indiquait 0.8.1 sur plusieurs bases).
- **Cause racine** (investiguee 2026-06-05) : migration PG17 Homebrew (bases restaurees le 2026-04-04). `age`/`pg_cron`/`vectorize` recompiles pour PG17 ; `age` recompile le 2026-05-03 et reinstalle **seulement** dans les 3 bases a graphe actif (medical/emails/genealogy). **`anon` jamais recompile pour PG17** (absent de `pg_available_extensions`, aucun `.control`/`.dylib`) → perdu de navig au restore. Donnees perdues = dictionnaires fictifs `anon.fake_*` (aucune PII reelle ; `raw.patients` synthetiques 20 lignes + ref/analytics intacts). Pas de DROP volontaire trace. Restauration : `age` **faite le 2026-06-05** (`CREATE EXTENSION age` dans finances/facturation_gmf/appsq) ; `anon` exige une recompilation depuis source (pgxn/git) pour PG17 — non fait.

### Audit rapide (SQL par base)

```sql
SELECT e.extname, e.extversion AS installed,
       a.default_version AS available,
       CASE WHEN e.extversion <> a.default_version THEN 'UPGRADE' ELSE 'ok' END AS status
FROM pg_extension e
JOIN pg_available_extensions a ON e.extname = a.name
WHERE e.extname <> 'plpgsql'
ORDER BY status DESC, e.extname;
```

Script d'audit complet: `~/.claude/plugins/intellisoins-plugins/intellisoins-postgresql/skills/local-databases-catalog/scripts/audit_extensions.sh`

## Instances Docker PostgreSQL

### intellisoins-postgres-local (port 6432)

Image: `intellisoins-pubmed-local-postgres`. User: `boost2`.

| Base           | Taille | Description                                        |
| -------------- | ------ | -------------------------------------------------- |
| boost2_billing | 51 MB  | App IntelliSoins PubMed (schema applicatif Prisma) |
| authentik_db   | 53 MB  | Authentik SSO (GoAuthentik)                        |

Connection: `psql -h localhost -p 6432 -U boost2 -d boost2_billing`

### postgresml (fork Rust natif Homebrew — extension installee dans 8 bases)

**Container Docker retire** (`ghcr.io/postgresml/postgresml:2.10.0`, port 5433) — absent de `docker ps -a`.
Fork local `postgresml-intellisoins` (Rust natif, pgrx) — source: `~/postgresml-build/`.

**Extension `pgml` installee dans 8 bases** (audit 2026-06-05). La lib partagee `.so` = **2.10.9** (commit 576020035 ; `pgml.version()` retourne 2.10.9 partout), mais le catalogue SQL de chaque base reste fige a sa version d'install tant qu'on n'execute pas `ALTER EXTENSION pgml UPDATE` :

| Base                                  | Catalogue SQL | Statut          |
| ------------------------------------- | :-----------: | --------------- |
| pgml_test, pgml_dashboard_development |    2.10.9     | a jour          |
| claude_usage                          |    2.10.8     | retard → UPDATE |
| mia5100z_course                       |    2.10.7     | retard → UPDATE |
| intelligence_artificielle             |    2.10.6     | retard → UPDATE |
| medical, finances, mia5100z           |    2.10.5     | retard → UPDATE |

Resync (catalogue SQL ↔ lib) : `ALTER EXTENSION pgml UPDATE;` par base. Nouvelle install ailleurs : `CREATE EXTENSION pgml CASCADE;` (dependances `vector` + `plpython3u`). Ne pas installer dans `postgres`, `litellm`, `litellm_pgvector` (systeme / app-gerees).

Usage in-database complet (`pgml.embed()`, `pgml.transform()`, `pgml.train()`, `pgml.predict()`, etc.):
voir rule dediee **`~/.claude/rules/postgresml-usage.md`** (chargee on-demand via `**/pgml*`, `**/postgresml*`).

Plugin Claude Code associe: `~/.claude/plugins/intellisoins-plugins/intellisoins-postgresml/`.

## Services ML associes

| Service              | Port | Usage                                     |
| -------------------- | ---- | ----------------------------------------- |
| Qwen3-Embedding-0.6B | 8084 | Embeddings 1024D pour indexation pgvector |
| BGE-reranker-v2-m3   | 8085 | Reranking pour recherche semantique       |

## Triggers d'enrichissement automatique

Triggers BEFORE INSERT/UPDATE installes sur les 4 bases actives (2026-03-17).
Se declenchent automatiquement a chaque indexation — aucune action manuelle requise.
Script d'installation: `organisateur-complet/scripts/install_enrichment_triggers.py`

| Base         | Table               | Trigger                         | Enrichissement                                                                                                       |
| ------------ | ------------------- | ------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| **medical**  | document_embeddings | `trg_enrich_document_embedding` | tsvector (weighted), language FR/EN, source_type, domain (pharmacie/recherche/admin), specialty (14 specialites)     |
| **emails**   | email_archive       | `trg_enrich_email_archive`      | tsvector (weighted), category (10 domaines par sender), importance, action_required, language                        |
| **finances** | document_embeddings | `trg_enrich_finance_document`   | tsvector (weighted), category (facture/releve/fiscal/pret/assurance/budget/contrat), language                        |
| **navig**    | documents_gmf       | `trg_enrich_document_gmf`       | tsvector (weighted), category (OC/procedure/formulaire/politique/reunion/formation/rapport), protocol_name, language |

```bash
python organisateur-complet/scripts/install_enrichment_triggers.py --status     # verification
python organisateur-complet/scripts/install_enrichment_triggers.py              # reinstallation (idempotent)
```

## Requetes utiles

```sql
-- Row counts par table
SELECT schemaname || '.' || relname AS table_name, n_live_tup AS rows
FROM pg_stat_user_tables ORDER BY n_live_tup DESC;

-- Structure d'une table
SELECT column_name, data_type, udt_name, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'transactions'
ORDER BY ordinal_position;

-- Index
SELECT indexname, tablename, indexdef
FROM pg_indexes WHERE schemaname = 'public' ORDER BY tablename;

-- Taille des tables
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC;
```

## References detaillees (schemas par colonne)

Les fichiers de reference detailles sont dans le plugin intellisoins-postgresql:
`~/.claude/plugins/intellisoins-plugins/intellisoins-postgresql/skills/local-databases-catalog/references/`

- **medical-schema.md** — Schema complet de la base medical (6 schemas, 85 tables)
- **finances-schema.md** — Schema complet de la base finances (32 tables, 29 vues)
- **boost2-schema.md** — Schema complet de la base facturation_gmf (ex-boost2_db, 8 schemas)
- **secondary-databases.md** — Schemas de emails, claude_usage, navig, genealogy, intellisoins-pubmed, etc.
- **extensions-upgrade.md** — Historique des mises a jour d'extensions, procedures
