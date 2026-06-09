"""
Smoke test RAGAs sur le pipeline kg_pipeline / medical DB.
Objectif : verifier que RAGAs produit 4 scores coherents (0..1) sur 3 cas.
PAS un benchmark — juste 'ca tourne sans crasher'.

Usage:
    source .venv-ragas/bin/activate
    export LITELLM_VIRTUAL_KEY=sk-...
    python3 ragas_smoke_test.py
"""

import json
import os
import sys
import psycopg
from ragas import evaluate
from ragas.dataset_schema import SingleTurnSample, EvaluationDataset
from ragas.metrics import (
    Faithfulness,
    ResponseRelevancy,
    LLMContextPrecisionWithReference,
    LLMContextRecall,
)
from ragas.llms import LangchainLLMWrapper
from langchain_openai import ChatOpenAI
from mlx_embeddings_client import MlxHttpEmbeddings

# ============================================================================
# CONFIG
# ============================================================================

DB_DSN = "postgresql:///medical"  # connexion locale via socket
LITELLM_BASE_URL = "http://localhost:8092"
LITELLM_KEY = os.environ.get("LITELLM_VIRTUAL_KEY")
JUDGE_MODEL = "claude-sonnet-4-6"
EMBED_BASE_URL = "http://localhost:8084"  # serveur MLX direct (bypass LiteLLM)
EMBED_MODEL = "Qwen/Qwen3-Embedding-0.6B"  # meme modele qui a peuple document_embeddings
TOP_K_CONTEXTS = 5

# 3 chunks PubMed CLINIQUES (vs precedent test sur meta-discours deprescription)
# Sujet: pharmacologie analgesique — gabapentine, pregabaline, ajustements IRC/hepatique
TEST_CASES = [
    {
        "chunk_id": 86624,
        "query": "Quelle est l'interaction pharmacocinetique entre la gabapentine et la morphine chez le volontaire sain ?",
        "reference": (
            "La gabapentine peut renforcer l'effet analgesique de la morphine. "
            "L'etude examine la pharmacocinetique de l'association gabapentine/morphine "
            "chez des volontaires sains, avec mesure des parametres PK et de l'analgesie."
        ),
    },
    {
        "chunk_id": 86628,
        "query": "La pregabaline reduit-elle la douleur aigue et la consommation de morphine en post-operatoire de cholecystectomie laparoscopique ?",
        "reference": (
            "Une meta-analyse d'essais randomises controles montre que la pregabaline "
            "diminue la douleur aigue et reduit la consommation de morphine chez les "
            "patients ayant subi une cholecystectomie laparoscopique."
        ),
    },
    {
        "chunk_id": 86630,
        "query": "Comment ajuster les analgesiques chez un patient avec insuffisance renale ou hepatique ?",
        "reference": (
            "La gestion pharmacologique de la douleur aigue chez le patient insuffisant "
            "renal ou hepatique requiert des ajustements posologiques specifiques. "
            "Les opioides et autres analgesiques ont une pharmacocinetique modifiee "
            "(metabolisme hepatique, excretion renale) et necessitent une surveillance accrue."
        ),
    },
]

# ============================================================================
# Sanity checks
# ============================================================================

if not LITELLM_KEY:
    print("ERREUR: LITELLM_VIRTUAL_KEY non defini.")
    print("  export LITELLM_VIRTUAL_KEY=$(grep '^LITELLM_VIRTUAL_KEY=' "
          "/Users/michaelahern/intellisoins-pubmed/.env.docker.local | cut -d= -f2-)")
    sys.exit(1)

print(f"LITELLM_VIRTUAL_KEY: {LITELLM_KEY[:8]}... ({len(LITELLM_KEY)} chars)")
print(f"Judge model: {JUDGE_MODEL} via {LITELLM_BASE_URL}")
print(f"Test cases: {len(TEST_CASES)}")
print()

# ============================================================================
# Pipeline : pour chaque cas, lancer kg_pipeline + retrieve + extraire answer
# ============================================================================

samples = []
with psycopg.connect(DB_DSN) as conn:
    with conn.cursor() as cur:
        for case in TEST_CASES:
            print(f"--- Cas chunk_id={case['chunk_id']} ---")

            # 1. Lancer le pipeline sur ce chunk
            try:
                cur.execute(
                    "SELECT kg_pipeline.run_chunk(%s, 0.5, true)",
                    [case["chunk_id"]],
                )
                run_id = cur.fetchone()[0]
                conn.commit()
                print(f"  run_id: {run_id}")
            except Exception as e:
                print(f"  ERREUR run_chunk: {e}")
                conn.rollback()
                continue

            # 2. Retrieve top-K chunks similaires via pgvector (halfvec cosine)
            cur.execute(
                """
                SELECT content_text
                FROM document_embeddings
                WHERE id != %s
                ORDER BY embedding <=>
                    (SELECT embedding FROM document_embeddings WHERE id = %s)
                LIMIT %s
                """,
                [case["chunk_id"], case["chunk_id"], TOP_K_CONTEXTS],
            )
            contexts = [row[0] for row in cur.fetchall()]
            print(f"  contexts retrieved: {len(contexts)} (longueurs: "
                  f"{[len(c) for c in contexts]})")

            # 3. Construire l'"answer" depuis les edge_candidates de ce run
            cur.execute(
                """
                SELECT
                    coalesce(em_src.entity_text, '?')
                    || ' -[' || coalesce(ec.relation_type, 'REL') || ']-> '
                    || coalesce(em_tgt.entity_text, '?')
                    AS edge,
                    ec.promotion_status,
                    ec.final_score,
                    ec.evidence_bge_score
                FROM kg_pipeline.edge_candidates ec
                LEFT JOIN kg_pipeline.entity_mentions em_src
                    ON ec.source_mention_id = em_src.id
                LEFT JOIN kg_pipeline.entity_mentions em_tgt
                    ON ec.target_mention_id = em_tgt.id
                WHERE ec.run_id = %s
                ORDER BY ec.final_score DESC NULLS LAST
                LIMIT 10
                """,
                [run_id],
            )
            edges = cur.fetchall()
            if edges:
                answer = "Relations extraites du chunk :\n" + "\n".join(
                    f"- {e[0]} (status={e[1]}, final={e[2]}, bge={e[3]})"
                    for e in edges
                )
            else:
                # Fallback : utiliser les mentions NER pures
                cur.execute(
                    """
                    SELECT entity_text, entity_label, ner_score
                    FROM kg_pipeline.entity_mentions
                    WHERE run_id = %s
                    ORDER BY ner_score DESC
                    LIMIT 20
                    """,
                    [run_id],
                )
                mentions = cur.fetchall()
                if mentions:
                    answer = (
                        "Entites extraites (aucune relation promue) :\n"
                        + "\n".join(
                            f"- {m[0]} [{m[1]}] (ner_score={m[2]:.2f})"
                            for m in mentions
                        )
                    )
                else:
                    answer = "(aucune entite ni relation extraite)"
            print(f"  edges: {len(edges)}, answer preview: "
                  f"{answer[:120].replace(chr(10), ' / ')}...")

            samples.append(
                SingleTurnSample(
                    user_input=case["query"],
                    retrieved_contexts=contexts,
                    response=answer,
                    reference=case["reference"],
                )
            )
            print()

if not samples:
    print("ERREUR: aucun sample produit, abandon.")
    sys.exit(4)

# ============================================================================
# Evaluation RAGAs
# ============================================================================

print(f"=== Evaluation RAGAs sur {len(samples)} cas ===")

llm = LangchainLLMWrapper(
    ChatOpenAI(
        model=JUDGE_MODEL,
        base_url=f"{LITELLM_BASE_URL}/v1",
        api_key=LITELLM_KEY,
        temperature=0,
    )
)

# Embeddings : client HTTP direct vers MLX :8084 (RAGAs-native, pas de langchain)
# Cohérent avec le modèle qui a peuplé document_embeddings.embedding (halfvec 1024D)
embeddings = MlxHttpEmbeddings(
    base_url=EMBED_BASE_URL,
    model=EMBED_MODEL,
)

try:
    results = evaluate(
        dataset=EvaluationDataset(samples=samples),
        metrics=[
            Faithfulness(llm=llm),
            ResponseRelevancy(llm=llm, embeddings=embeddings),
            LLMContextPrecisionWithReference(llm=llm),
            LLMContextRecall(llm=llm),
        ],
    )
except Exception as e:
    print(f"ERREUR evaluate(): {e}")
    sys.exit(2)

# ============================================================================
# Output
# ============================================================================

df = results.to_pandas()
print("\n=== RESULTATS PAR CAS ===")
# Ne montrer que les colonnes scores pour rester lisible
score_cols = [c for c in df.columns if c not in
              ("user_input", "retrieved_contexts", "response", "reference")]
print(df[score_cols].to_string())

print("\n=== SCORES AGREGES (moyenne) ===")
print(df[score_cols].mean().to_string())

# Sauvegarder
out_path = "/tmp/ragas_smoke_results.json"
with open(out_path, "w") as f:
    json.dump(df.to_dict(orient="records"), f, indent=2,
              ensure_ascii=False, default=str)
print(f"\nDetail sauvegarde : {out_path}")

# Verdict smoke test
import pandas as pd
faith = df.get("faithfulness", pd.Series([float("nan")]))
relev = df.get("answer_relevancy", pd.Series([float("nan")]))

if faith.isna().all() or relev.isna().all():
    print("\nFAIL : scores NaN — le pipeline produit un format que RAGAs ne sait pas scorer")
    sys.exit(2)
elif faith.mean() == 0 and relev.mean() == 0:
    print("\nFAIL : tous les scores critiques a 0 — retrieval/answer cassees")
    sys.exit(3)
else:
    print(f"\nPASS : RAGAs tourne. faithfulness moyen = {faith.mean():.3f}, "
          f"answer_relevancy moyen = {relev.mean():.3f}")
    print("Tu peux investir dans un vrai benchmark.")
