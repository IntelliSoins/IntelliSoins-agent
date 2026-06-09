# Medical KG Pipeline Reference

## Local Setup

Project cwd for service control:

```bash
cd /Users/michaelahern/ai-servers
```

Database:

- PostgreSQL database: `medical`
- pipeline schema: `kg_pipeline`
- relation tables: `public.kg_entities`, `public.kg_relations`
- AGE graph: `medical_graph`

Local services:

| Capability            | Endpoint                              |
| --------------------- | ------------------------------------- |
| GLiNER biomedical NER | `http://127.0.0.1:8091/extract`       |
| Embeddings            | `http://127.0.0.1:8084/v1/embeddings` |
| BGE reranker          | `http://127.0.0.1:8085/v1/rerank`     |

Check services:

```bash
./aictl status
./aictl health
```

## Pipeline Shape

Canonical flow:

```text
chunk -> GLiNER entities -> entity linking -> edge candidate
      -> BGE evidence score -> ontology validation -> kg_relations
      -> optional AGE promotion
```

Main functions:

```sql
SELECT kg_pipeline.run_chunk(126, 0.5, true);

SELECT kg_pipeline.run_document_embeddings(
  25,
  ARRAY['deprx_alternatives','deprx_stopp_fall','pubmed'],
  0.5,
  true
);
```

Core tables:

```sql
SELECT run_id, status, chunks_processed, mentions_count,
       edge_candidates_count, relations_promoted_count,
       age_nodes_created, age_edges_created, error
FROM kg_pipeline.runs
ORDER BY started_at DESC
LIMIT 10;

SELECT promotion_status, relation_type, final_score, evidence_bge_score,
       kg_relation_id, properties->>'source_text' AS source,
       properties->>'target_text' AS target
FROM kg_pipeline.edge_candidates
ORDER BY created_at DESC
LIMIT 20;
```

AGE inspection:

```sql
LOAD 'age';
SET search_path = ag_catalog, public;

SELECT * FROM cypher(
  'medical_graph',
  $$MATCH (n) RETURN count(n) AS nodes$$
) AS (nodes agtype);

SELECT * FROM cypher(
  'medical_graph',
  $$MATCH ()-[r]->() RETURN count(r) AS edges$$
) AS (edges agtype);
```

## Clinical Query Pattern

For a request like `douleur chronique et esketamine`:

1. Count exact matches in `document_embeddings` or the relevant corpus.
2. Run semantic retrieval through pgvector.
3. Rerank candidates with BGE.
4. Inspect whether evidence says `esketamine` directly or only nearby concepts
   such as `ketamine`, `chronic pain`, or `CRPS`.
5. Do not promote a relation if evidence is only semantic proximity.

Useful output categories:

- direct evidence: exact topic appears in retrieved text and reranker supports it
- indirect evidence: related molecule or disease appears, but not the exact query
- no promotion: evidence is insufficient for a KG edge
- candidate promotion: evidence is strong enough to keep as `edge_candidate`
- KG promotion: relation exists in `public.kg_relations`
- AGE promotion: relation is visible in `medical_graph`

## SNOMED Import

Adapted local script:

```bash
cd /Users/michaelahern/ai-servers

python3 scripts/import_snomed_medical.py --dry-run --no-checksum --limit-concepts 5
python3 scripts/import_snomed_medical.py
python3 scripts/import_snomed_medical.py --promote-age
python3 scripts/import_snomed_medical.py --promote-existing
```

Source RF2 bundle:

```text
/Users/michaelahern/intellisoins-pubmed/data/snomed_fr_can/SNOMED_CT_CA_RF2_Release_20260228.zip
```

Target mapping:

- concepts -> `public.kg_entities`
- `entity_type='SnomedConcept'`
- namespace `snomed_ca_20260228`
- IS_A hierarchy -> `public.kg_relations`
- `relation_type='SOUS_TYPE_DE'`

Do not run a full SNOMED import just to answer a query unless Michael explicitly
wants to load the ontology.

## Validation Notes

Initial validated smoke run:

- run id: `6f0cdd99-5d49-4007-b037-eab2261a1e5e`
- 14 mentions
- 23 edge candidates
- 2 relations promoted
- 2 AGE nodes and 2 AGE edges created

Quality note:

- an earlier run `166e4197-fff7-47c7-b95c-53ba73e57718` was marked superseded
  after vector-linking was tightened
- vector linking excludes entities created by `kg_pipeline` to avoid
  over-merging new entities into each other
