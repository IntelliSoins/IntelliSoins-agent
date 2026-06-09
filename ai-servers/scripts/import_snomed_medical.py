#!/usr/bin/env python3
"""
Import SNOMED CT Canada RF2 into Michael's local medical PostgreSQL KG.

Adapted from intellisoins-pubmed/scripts/import-snomed-concepts.ts and
import-snomed-relationships.ts.

This version is SQL-first for the local `medical` database:
  - concepts are inserted into public.kg_entities as entity_type='SnomedConcept'
  - IS_A hierarchy is inserted into public.kg_relations as relation_type='SOUS_TYPE_DE'
  - optional AGE promotion writes nodes/edges into the `medical_graph` graph

Default mode is conservative: parse and import concepts + hierarchy into the
relational KG, but do not promote to AGE unless --promote-age is passed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import uuid
import zipfile
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import psycopg2
from psycopg2.extras import Json, execute_values


def raise_csv_field_limit() -> None:
    """Allow very large RF2 text fields without depending on platform max size."""
    limit = sys.maxsize
    while True:
        try:
            csv.field_size_limit(limit)
            return
        except OverflowError:
            limit //= 10


raise_csv_field_limit()


SOURCE_ROOT = Path("/Users/michaelahern/intellisoins-pubmed")
DEFAULT_DSN = "host=localhost dbname=medical user=michaelahern"
DEFAULT_NAMESPACE = "snomed_ca_20260228"
DEFAULT_GRAPH = "medical_graph"
BATCH_SIZE = 500

CLINICAL_FINDING_ROOT = "404684003"
IS_A_TYPE_ID = "116680003"
FSN_TYPE_ID = "900000000000003001"
SYNONYM_TYPE_ID = "900000000000013009"
CANADA_FR_REFSET_ID = "20581000087109"
PREFERRED_ACCEPTABILITY_ID = "900000000000548007"
SNOMED_NODE_ID_PREFIX = "snomed_"

CONCEPT_COL = {"id": 0, "effectiveTime": 1, "active": 2}
DESC_COL = {
    "id": 0,
    "active": 2,
    "conceptId": 4,
    "languageCode": 5,
    "typeId": 6,
    "term": 7,
}
LANG_COL = {
    "active": 2,
    "refsetId": 4,
    "referencedComponentId": 5,
    "acceptabilityId": 6,
}
REL_COL = {
    "active": 2,
    "sourceId": 4,
    "destinationId": 5,
    "typeId": 7,
}


@dataclass
class DescriptionEntry:
    fsn_en: str = ""
    fsn_fr: str = ""
    preferred_term_en: str = ""
    description_ids_fr: list[str] | None = None

    def __post_init__(self) -> None:
        if self.description_ids_fr is None:
            self.description_ids_fr = []


@dataclass
class ConceptRow:
    concept_id: str
    node_id: str
    name: str
    fully_specified_name: str
    preferred_term_en: str
    preferred_term_fr: str
    semantic_type: str
    nom_normalized: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    parser.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    parser.add_argument("--graph", default=DEFAULT_GRAPH)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-concepts", action="store_true")
    parser.add_argument("--skip-relationships", action="store_true")
    parser.add_argument("--promote-age", action="store_true")
    parser.add_argument(
        "--promote-existing",
        action="store_true",
        help="promote already imported SNOMED rows from kg_entities/kg_relations to AGE",
    )
    parser.add_argument("--limit-concepts", type=int)
    parser.add_argument("--limit-relationships", type=int)
    parser.add_argument("--no-checksum", action="store_true")
    return parser.parse_args()


def assert_sctid(value: str, context: str) -> None:
    if not re.fullmatch(r"\d+", value or ""):
        raise ValueError(f"{context}: invalid SNOMED SCTID {value!r}")


def snomed_node_id(concept_id: str) -> str:
    assert_sctid(concept_id, "snomed_node_id")
    return f"{SNOMED_NODE_ID_PREFIX}{concept_id}"


def parse_semantic_tag(fsn: str) -> str:
    match = re.search(r"\(([^)]+)\)$", fsn or "")
    return match.group(1) if match else ""


def normalize_concept_name(fsn: str) -> str:
    return re.sub(r"\s*\([^)]*\)$", "", fsn or "").strip().lower()


def display_name(row: ConceptRow) -> str:
    base = row.preferred_term_fr or row.preferred_term_en or normalize_concept_name(row.fully_specified_name)
    base = base or row.concept_id
    # public.kg_entities has UNIQUE(entity_type, name, namespace). The SCTID suffix
    # preserves uniqueness without losing the readable term.
    return f"{base} (SNOMED {row.concept_id})"


def load_checksums(source_root: Path) -> dict:
    path = source_root / "scripts" / "snomed-rf2-checksums.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def bundle_path(source_root: Path, checksums: dict) -> Path:
    filename = checksums["bundle"]["filename"]
    return source_root / "data" / "snomed_fr_can" / filename


def verify_sha256(path: Path, expected: str) -> None:
    print(f"[sha256] verifying {path}")
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    actual = h.hexdigest()
    if actual != expected:
        raise RuntimeError(f"SNOMED bundle SHA256 mismatch: expected {expected}, got {actual}")
    print(f"[sha256] OK {actual}")


def find_member(zf: zipfile.ZipFile, pattern: str) -> str:
    regex = re.compile(pattern)
    matches = [n for n in zf.namelist() if "/Snapshot/" in n and regex.search(Path(n).name)]
    if not matches:
        raise FileNotFoundError(f"no ZIP member matching {pattern}")
    if len(matches) > 1:
        raise RuntimeError(f"ambiguous ZIP member for {pattern}: {matches[:5]}")
    return matches[0]


def stream_tsv(zf: zipfile.ZipFile, member: str) -> Iterable[list[str]]:
    with zf.open(member, "r") as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8", newline="")
        reader = csv.reader(text, delimiter="\t")
        next(reader, None)  # header
        for row in reader:
            if row:
                # RF2 is CRLF; csv handles CRLF but keep fields clean defensively.
                yield [col.rstrip("\r") for col in row]


def build_clinical_finding_ids(zf: zipfile.ZipFile, relationship_member: str) -> set[str]:
    print(f"[pass 1] BFS clinical findings from {Path(relationship_member).name}")
    adjacency: dict[str, set[str]] = defaultdict(set)
    rows = active_is_a = 0
    for cols in stream_tsv(zf, relationship_member):
        if len(cols) < 10:
            continue
        rows += 1
        if cols[REL_COL["active"]] != "1" or cols[REL_COL["typeId"]] != IS_A_TYPE_ID:
            continue
        active_is_a += 1
        child = cols[REL_COL["sourceId"]]
        parent = cols[REL_COL["destinationId"]]
        adjacency[parent].add(child)

    visited = {CLINICAL_FINDING_ROOT}
    queue: deque[str] = deque([CLINICAL_FINDING_ROOT])
    while queue:
        current = queue.popleft()
        for child in adjacency.get(current, ()):
            if child in visited:
                continue
            visited.add(child)
            queue.append(child)

    print(f"[pass 1] rows={rows} active_is_a={active_is_a} clinical_findings={len(visited)}")
    return visited


def build_description_maps(
    zf: zipfile.ZipFile,
    description_member: str,
    clinical_ids: set[str],
) -> tuple[dict[str, DescriptionEntry], dict[str, str]]:
    print(f"[pass 2] descriptions from {Path(description_member).name}")
    desc_map: dict[str, DescriptionEntry] = {}
    desc_id_to_term: dict[str, str] = {}
    rows = matched = 0
    for cols in stream_tsv(zf, description_member):
        if len(cols) < 9:
            continue
        rows += 1
        if cols[DESC_COL["active"]] != "1":
            continue
        concept_id = cols[DESC_COL["conceptId"]]
        if concept_id not in clinical_ids:
            continue
        type_id = cols[DESC_COL["typeId"]]
        lang = cols[DESC_COL["languageCode"]]
        if type_id not in (FSN_TYPE_ID, SYNONYM_TYPE_ID) or lang not in ("en", "fr"):
            continue
        matched += 1
        entry = desc_map.setdefault(concept_id, DescriptionEntry())
        desc_id = cols[DESC_COL["id"]]
        term = cols[DESC_COL["term"]]
        if type_id == FSN_TYPE_ID and lang == "en" and not entry.fsn_en:
            entry.fsn_en = term
        if type_id == FSN_TYPE_ID and lang == "fr" and not entry.fsn_fr:
            entry.fsn_fr = term
        if type_id == SYNONYM_TYPE_ID and lang == "en" and not entry.preferred_term_en:
            entry.preferred_term_en = term
        if lang == "fr":
            entry.description_ids_fr.append(desc_id)
            desc_id_to_term.setdefault(desc_id, term)
    print(f"[pass 2] rows={rows} matched={matched} concepts_with_desc={len(desc_map)}")
    return desc_map, desc_id_to_term


def build_preferred_fr_map(
    zf: zipfile.ZipFile,
    language_member: str,
    desc_map: dict[str, DescriptionEntry],
) -> dict[str, str]:
    print(f"[pass 3] Canada FR preferred terms from {Path(language_member).name}")
    desc_id_to_concept: dict[str, str] = {}
    for concept_id, entry in desc_map.items():
        for desc_id in entry.description_ids_fr:
            desc_id_to_concept[desc_id] = concept_id

    preferred: dict[str, str] = {}
    rows = matched = 0
    for cols in stream_tsv(zf, language_member):
        if len(cols) < 7:
            continue
        rows += 1
        if cols[LANG_COL["active"]] != "1":
            continue
        if cols[LANG_COL["refsetId"]] != CANADA_FR_REFSET_ID:
            continue
        if cols[LANG_COL["acceptabilityId"]] != PREFERRED_ACCEPTABILITY_ID:
            continue
        desc_id = cols[LANG_COL["referencedComponentId"]]
        concept_id = desc_id_to_concept.get(desc_id)
        if not concept_id:
            continue
        matched += 1
        preferred.setdefault(concept_id, desc_id)
    print(f"[pass 3] rows={rows} matched={matched} concepts_with_preferred_fr={len(preferred)}")
    return preferred


def iter_concepts(
    zf: zipfile.ZipFile,
    concept_member: str,
    clinical_ids: set[str],
    desc_map: dict[str, DescriptionEntry],
    preferred_fr_by_concept: dict[str, str],
    desc_id_to_term: dict[str, str],
    limit: int | None,
) -> Iterable[ConceptRow]:
    emitted = 0
    for cols in stream_tsv(zf, concept_member):
        if len(cols) < 5:
            continue
        if cols[CONCEPT_COL["active"]] != "1":
            continue
        concept_id = cols[CONCEPT_COL["id"]]
        if concept_id not in clinical_ids:
            continue
        assert_sctid(concept_id, "iter_concepts")
        entry = desc_map.get(concept_id, DescriptionEntry())
        fsn = entry.fsn_en
        preferred_en = entry.preferred_term_en or fsn
        preferred_fr = ""
        preferred_fr_desc_id = preferred_fr_by_concept.get(concept_id)
        if preferred_fr_desc_id:
            preferred_fr = desc_id_to_term.get(preferred_fr_desc_id, "")
        if not preferred_fr and entry.fsn_fr:
            preferred_fr = entry.fsn_fr
        row = ConceptRow(
            concept_id=concept_id,
            node_id=snomed_node_id(concept_id),
            name="",
            fully_specified_name=fsn,
            preferred_term_en=preferred_en,
            preferred_term_fr=preferred_fr,
            semantic_type=parse_semantic_tag(fsn),
            nom_normalized=normalize_concept_name(fsn),
        )
        row.name = display_name(row)
        yield row
        emitted += 1
        if limit and emitted >= limit:
            return


def ensure_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        cur.execute("CREATE SCHEMA IF NOT EXISTS kg_pipeline")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS kg_pipeline.snomed_import_runs (
              import_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
              status text NOT NULL DEFAULT 'running',
              namespace text NOT NULL,
              release_date text,
              source_bundle text,
              clinical_finding_count integer NOT NULL DEFAULT 0,
              concepts_inserted integer NOT NULL DEFAULT 0,
              relationships_inserted integer NOT NULL DEFAULT 0,
              age_nodes_created integer NOT NULL DEFAULT 0,
              age_edges_created integer NOT NULL DEFAULT 0,
              started_at timestamptz NOT NULL DEFAULT now(),
              completed_at timestamptz,
              error text
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_kg_entities_snomed_concept_id
            ON public.kg_entities ((properties->>'concept_id'))
            WHERE entity_type = 'SnomedConcept'
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_kg_entities_snomed_node_id
            ON public.kg_entities ((properties->>'node_id'))
            WHERE entity_type = 'SnomedConcept'
            """
        )
    conn.commit()


def create_import_run(conn, namespace: str, release_date: str, source_bundle: str) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO kg_pipeline.snomed_import_runs(namespace, release_date, source_bundle)
            VALUES (%s, %s, %s)
            RETURNING import_id
            """,
            (namespace, release_date, source_bundle),
        )
        import_id = str(cur.fetchone()[0])
    conn.commit()
    return import_id


def finish_import_run(conn, import_id: str, status: str, **counts: int | str | None) -> None:
    fields = ["status = %s", "completed_at = now()"]
    values: list[object] = [status]
    for key, value in counts.items():
        fields.append(f"{key} = %s")
        values.append(value)
    values.append(import_id)
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE kg_pipeline.snomed_import_runs SET {', '.join(fields)} WHERE import_id = %s",
            values,
        )
    conn.commit()


def insert_concepts(
    conn,
    rows: list[ConceptRow],
    namespace: str,
    import_id: str,
    release_date: str,
    source_bundle: str,
) -> int:
    if not rows:
        return 0
    values = []
    for row in rows:
        props = {
            "source": "snomed_ct_ca_rf2",
            "import_id": import_id,
            "node_id": row.node_id,
            "concept_id": row.concept_id,
            "fully_specified_name": row.fully_specified_name,
            "preferred_term_en": row.preferred_term_en,
            "preferred_term_fr": row.preferred_term_fr,
            "semantic_type": row.semantic_type,
            "nom_normalized": row.nom_normalized,
            "release_date": release_date,
            "source_bundle": source_bundle,
        }
        values.append(("SnomedConcept", row.name, Json(props), namespace))
    sql = """
        INSERT INTO public.kg_entities(entity_type, name, properties, namespace, created_at, updated_at)
        VALUES %s
        ON CONFLICT (entity_type, name, namespace)
        DO UPDATE SET
          properties = public.kg_entities.properties || EXCLUDED.properties,
          updated_at = now()
        RETURNING id
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, values, page_size=len(values))
        inserted = len(cur.fetchall())
    conn.commit()
    return inserted


def load_concept_entity_ids(conn, namespace: str) -> dict[str, int]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT properties->>'concept_id', id
            FROM public.kg_entities
            WHERE entity_type = 'SnomedConcept'
              AND namespace = %s
              AND properties ? 'concept_id'
            """,
            (namespace,),
        )
        return {concept_id: entity_id for concept_id, entity_id in cur.fetchall()}


def insert_relationship_batch(
    conn,
    batch: list[tuple[int, int, str, str]],
    import_id: str,
    release_date: str,
) -> int:
    if not batch:
        return 0
    values = []
    for source_entity_id, target_entity_id, source_concept_id, target_concept_id in batch:
        props = {
            "source": "snomed_ct_ca_rf2",
            "import_id": import_id,
            "source_concept_id": source_concept_id,
            "target_concept_id": target_concept_id,
            "snomed_type_id": IS_A_TYPE_ID,
            "release_date": release_date,
        }
        values.append((source_entity_id, target_entity_id, "SOUS_TYPE_DE", Json(props), 1.0, None))
    sql = """
        INSERT INTO public.kg_relations(
          source_entity_id, target_entity_id, relation_type, properties, confidence, source_chunk_id, created_at
        )
        VALUES %s
        ON CONFLICT (source_entity_id, target_entity_id, relation_type)
        DO NOTHING
        RETURNING id
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, values, page_size=len(values))
        inserted = len(cur.fetchall())
    conn.commit()
    return inserted


def import_relationships(
    conn,
    zf: zipfile.ZipFile,
    relationship_member: str,
    clinical_ids: set[str],
    concept_entity_ids: dict[str, int],
    import_id: str,
    release_date: str,
    batch_size: int,
    limit: int | None,
) -> int:
    inserted = 0
    scanned = filtered = 0
    batch: list[tuple[int, int, str, str]] = []
    for cols in stream_tsv(zf, relationship_member):
        if len(cols) < 10:
            continue
        scanned += 1
        if cols[REL_COL["active"]] != "1" or cols[REL_COL["typeId"]] != IS_A_TYPE_ID:
            continue
        source_id = cols[REL_COL["sourceId"]]
        target_id = cols[REL_COL["destinationId"]]
        if source_id not in clinical_ids or target_id not in clinical_ids:
            continue
        if source_id not in concept_entity_ids or target_id not in concept_entity_ids:
            continue
        assert_sctid(source_id, "import_relationships.source")
        assert_sctid(target_id, "import_relationships.target")
        filtered += 1
        batch.append((concept_entity_ids[source_id], concept_entity_ids[target_id], source_id, target_id))
        if len(batch) >= batch_size:
            inserted += insert_relationship_batch(conn, batch, import_id, release_date)
            batch = []
            print(f"[relationships] inserted={inserted} scanned={scanned} filtered={filtered}")
        if limit and filtered >= limit:
            break
    if batch:
        inserted += insert_relationship_batch(conn, batch, import_id, release_date)
    print(f"[relationships] done inserted={inserted} scanned={scanned} filtered={filtered}")
    return inserted


def cypher_literal(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def cypher_ident(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", value or "")
    if not cleaned:
        return "Entity"
    if cleaned[0].isdigit():
        return "Entity" + cleaned
    return cleaned


def run_cypher(conn, graph: str, query: str) -> int:
    delim = f"$q_{uuid.uuid4().hex}$"
    sql = f"SELECT value::text FROM cypher({cypher_literal(graph)}, {delim}{query}{delim}) AS (value agtype)"
    with conn.cursor() as cur:
        cur.execute("LOAD 'age'")
        cur.execute("SET search_path = ag_catalog, public")
        cur.execute(sql)
        row = cur.fetchone()
    conn.commit()
    return int(str(row[0])) if row else 0


def promote_age_nodes(conn, graph: str, namespace: str, batch_size: int) -> int:
    created = 0
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, properties->>'concept_id', properties->>'preferred_term_fr',
                   properties->>'preferred_term_en', properties->>'semantic_type',
                   properties->>'node_id'
            FROM public.kg_entities
            WHERE entity_type = 'SnomedConcept' AND namespace = %s
            ORDER BY id
            """,
            (namespace,),
        )
        batch = cur.fetchmany(batch_size)
        while batch:
            items = []
            for entity_id, name, concept_id, fr, en, semantic_type, node_id in batch:
                items.append(
                    "{"
                    f"kg_entity_id: {int(entity_id)}, "
                    f"name: {cypher_literal(name or '')}, "
                    f"concept_id: {cypher_literal(concept_id or '')}, "
                    f"preferred_term_fr: {cypher_literal(fr or '')}, "
                    f"preferred_term_en: {cypher_literal(en or '')}, "
                    f"semantic_type: {cypher_literal(semantic_type or '')}, "
                    f"id: {cypher_literal(node_id or snomed_node_id(concept_id or '0'))}"
                    "}"
                )
            query = (
                f"UNWIND [{','.join(items)}] AS row "
                "MERGE (n:SnomedConcept {kg_entity_id: row.kg_entity_id}) "
                "SET n.id = row.id, n.name = row.name, n.concept_id = row.concept_id, "
                "n.preferred_term_fr = row.preferred_term_fr, "
                "n.preferred_term_en = row.preferred_term_en, "
                "n.semantic_type = row.semantic_type "
                "RETURN count(n)"
            )
            created += run_cypher(conn, graph, query)
            print(f"[age nodes] merged_total={created}")
            batch = cur.fetchmany(batch_size)
    return created


def promote_age_edges(
    conn,
    graph: str,
    import_id: str | None,
    namespace: str,
    batch_size: int,
) -> int:
    created = 0
    with conn.cursor() as cur:
        if import_id:
            cur.execute(
                """
                SELECT r.id, r.source_entity_id, r.target_entity_id, r.relation_type
                FROM public.kg_relations r
                WHERE r.relation_type = 'SOUS_TYPE_DE'
                  AND r.properties->>'import_id' = %s
                ORDER BY r.id
                """,
                (import_id,),
            )
        else:
            cur.execute(
                """
                SELECT r.id, r.source_entity_id, r.target_entity_id, r.relation_type
                FROM public.kg_relations r
                JOIN public.kg_entities s ON s.id = r.source_entity_id
                JOIN public.kg_entities t ON t.id = r.target_entity_id
                WHERE r.relation_type = 'SOUS_TYPE_DE'
                  AND s.entity_type = 'SnomedConcept'
                  AND t.entity_type = 'SnomedConcept'
                  AND s.namespace = %s
                  AND t.namespace = %s
                ORDER BY r.id
                """,
                (namespace, namespace),
            )
        batch = cur.fetchmany(batch_size)
        while batch:
            items = []
            for relation_id, source_id, target_id, relation_type in batch:
                items.append(
                    "{"
                    f"kg_relation_id: {int(relation_id)}, "
                    f"source_entity_id: {int(source_id)}, "
                    f"target_entity_id: {int(target_id)}, "
                    f"relation_type: {cypher_literal(relation_type)}"
                    "}"
                )
            rel_label = cypher_ident("SOUS_TYPE_DE")
            query = (
                f"UNWIND [{','.join(items)}] AS row "
                "MATCH (s:SnomedConcept {kg_entity_id: row.source_entity_id}) "
                "MATCH (t:SnomedConcept {kg_entity_id: row.target_entity_id}) "
                f"MERGE (s)-[r:{rel_label} {{kg_relation_id: row.kg_relation_id}}]->(t) "
                "SET r.relation_type = row.relation_type "
                "RETURN count(r)"
            )
            created += run_cypher(conn, graph, query)
            print(f"[age edges] merged_total={created}")
            batch = cur.fetchmany(batch_size)
    return created


def main() -> int:
    args = parse_args()
    if args.promote_existing:
        conn = psycopg2.connect(args.dsn)
        try:
            ensure_schema(conn)
            age_nodes = promote_age_nodes(conn, args.graph, args.namespace, args.batch_size)
            age_edges = promote_age_edges(conn, args.graph, None, args.namespace, args.batch_size)
            print("[done]")
            print(f"  promoted_existing_namespace={args.namespace}")
            print(f"  age_nodes_created={age_nodes}")
            print(f"  age_edges_created={age_edges}")
        finally:
            conn.close()
        return 0

    checksums = load_checksums(args.source_root)
    release_date = checksums["bundle"]["release_date"]
    bundle = bundle_path(args.source_root, checksums)
    if not bundle.exists():
        raise FileNotFoundError(bundle)
    if not args.no_checksum:
        verify_sha256(bundle, checksums["bundle"]["sha256"])

    with zipfile.ZipFile(bundle) as zf:
        concept_member = find_member(zf, r"sct2_Concept_Snapshot.*\.txt$")
        desc_member = find_member(zf, r"sct2_Description_Snapshot.*\.txt$")
        lang_member = find_member(zf, r"der2_cRefset_LanguageSnapshot.*\.txt$")
        rel_member = find_member(zf, r"sct2_Relationship_Snapshot.*\.txt$")
        print("[rf2] files")
        print(f"  concept      {concept_member}")
        print(f"  description  {desc_member}")
        print(f"  language     {lang_member}")
        print(f"  relationship {rel_member}")

        clinical_ids = build_clinical_finding_ids(zf, rel_member)
        desc_map, desc_id_to_term = build_description_maps(zf, desc_member, clinical_ids)
        preferred_fr = build_preferred_fr_map(zf, lang_member, desc_map)

        if args.dry_run:
            sample = list(iter_concepts(
                zf, concept_member, clinical_ids, desc_map, preferred_fr,
                desc_id_to_term, args.limit_concepts or 5,
            ))
            print("[dry-run] sample concepts")
            for row in sample:
                print(json.dumps(row.__dict__, ensure_ascii=False))
            print(f"[dry-run] clinical_finding_count={len(clinical_ids)}")
            return 0

        conn = psycopg2.connect(args.dsn)
        try:
            ensure_schema(conn)
            import_id = create_import_run(conn, args.namespace, release_date, str(bundle))
            concepts_inserted = relationships_inserted = age_nodes = age_edges = 0
            print(f"[run] import_id={import_id}")

            if not args.skip_concepts:
                batch: list[ConceptRow] = []
                for row in iter_concepts(
                    zf, concept_member, clinical_ids, desc_map, preferred_fr,
                    desc_id_to_term, args.limit_concepts,
                ):
                    batch.append(row)
                    if len(batch) >= args.batch_size:
                        concepts_inserted += insert_concepts(
                            conn, batch, args.namespace, import_id, release_date, str(bundle)
                        )
                        print(f"[concepts] inserted={concepts_inserted}")
                        batch = []
                if batch:
                    concepts_inserted += insert_concepts(
                        conn, batch, args.namespace, import_id, release_date, str(bundle)
                    )
                    print(f"[concepts] inserted={concepts_inserted}")

            if not args.skip_relationships:
                concept_entity_ids = load_concept_entity_ids(conn, args.namespace)
                relationships_inserted = import_relationships(
                    conn, zf, rel_member, clinical_ids, concept_entity_ids, import_id,
                    release_date, args.batch_size, args.limit_relationships,
                )

            if args.promote_age:
                age_nodes = promote_age_nodes(conn, args.graph, args.namespace, args.batch_size)
                age_edges = promote_age_edges(conn, args.graph, import_id, args.namespace, args.batch_size)

            finish_import_run(
                conn,
                import_id,
                "completed",
                clinical_finding_count=len(clinical_ids),
                concepts_inserted=concepts_inserted,
                relationships_inserted=relationships_inserted,
                age_nodes_created=age_nodes,
                age_edges_created=age_edges,
            )
            print("[done]")
            print(f"  import_id={import_id}")
            print(f"  concepts_inserted={concepts_inserted}")
            print(f"  relationships_inserted={relationships_inserted}")
            print(f"  age_nodes_created={age_nodes}")
            print(f"  age_edges_created={age_edges}")
        except Exception as exc:
            conn.rollback()
            if "import_id" in locals():
                finish_import_run(conn, import_id, "failed", error=str(exc))
            raise
        finally:
            conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
