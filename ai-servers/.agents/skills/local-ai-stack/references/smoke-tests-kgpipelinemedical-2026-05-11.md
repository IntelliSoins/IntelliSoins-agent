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
