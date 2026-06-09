---
name: ner-rag-kg-reranking
description: |
  Operate, test, and diagnose Michael's local medical NER, RAG, pgvector, KG,
  BGE reranking, and Apache AGE pipeline. Use this project skill whenever the
  user mentions NER-RAG-KG-reranking, kg_pipeline, GLiNER biomedical NER,
  pgvector embeddings, BGE reranker, SNOMED KG, Apache AGE medical_graph,
  edge candidates, ontology validation, or asks to test a clinical query
  against the local `medical` database.
---

# NER RAG KG Reranking

## Scope

Use this skill for the local `medical` setup connected to
`/Users/michaelahern/ai-servers`.

The pipeline combines:

- GLiNER biomedical NER on port `8091`
- embeddings/RAG via pgvector and local endpoint `8084`
- BGE reranking on port `8085`
- relation tables `public.kg_entities` and `public.kg_relations`
- optional Apache AGE promotion into graph `medical_graph`

Load `references/medical-kg-pipeline.md` only when commands, SQL, or deeper
diagnostic detail are needed.

## Workflow

1. Check service state from `/Users/michaelahern/ai-servers`:
   - `./aictl status`
   - `./aictl health`
2. Verify GLiNER `8091`, embeddings `8084`, and reranker `8085` before a
   pipeline test.
3. Verify PostgreSQL state before drawing conclusions:
   - schema `kg_pipeline`
   - tables `kg_pipeline.runs`, `entity_mentions`, `edge_candidates`
   - tables `public.kg_entities`, `public.kg_relations`
   - AGE graph `medical_graph`
4. Prefer a targeted `kg_pipeline.run_chunk(...)` smoke before batch work.
5. For clinical retrieval, separate exact keyword evidence, semantic neighbors,
   reranker support, candidate edges, promoted KG relations, and AGE state.

## Guardrails

- Do not treat semantic proximity as a validated clinical relation.
- Require text evidence and reranking support before creating or promoting an edge.
- Do not run the full SNOMED import unless Michael explicitly asks for it.
- Do not promote to AGE by default; use promotion flags only when intended.
- If NER linking looks over-merged, inspect `entity_mentions` and
  `edge_candidates` before changing linkage behavior.

## Expected Output

When answering Michael, include:

- concrete local service and PostgreSQL status
- commands or SQL executed
- useful counters such as mentions, edge candidates, promoted relations,
  AGE nodes, and AGE edges
- a cautious technical or clinical conclusion separated from local evidence
