#!/usr/bin/env python3
"""Ingestion de documents dans le vector store pgvector dedie au projet OpenClaw.

Pipeline 100% local (Loi 25):
  document (PDF/DOCX/MD/HTML/image)
    -> Docling chunk hybrid (:5010, OCR ocrmac natif Apple Vision)
    -> embeddings qwen3-embedding 1024D via LiteLLM proxy (:8092)
    -> insertion batch sidecar litellm-pgvector-openclaw (:8100, DB openclaw_pgvector)

Usage:
  python3 openclaw_rag_ingest.py [fichier_ou_dossier ...]
    (defaut: ~/openclaw/rag-documents/)
  python3 openclaw_rag_ingest.py --query "ma question"   # smoke search apres ingestion

Cles lues dans le Keychain macOS (jamais hardcodees):
  litellm-master-key (proxy 8092), litellm-pgvector-api-key (sidecar 8100).
"""

from __future__ import annotations  # requis: le gateway launchd spawn /usr/bin/python3 (3.9)

import argparse
import json
import pathlib
import subprocess
import sys
import time
import urllib.request

DOCLING = "http://127.0.0.1:5010"
PROXY = "http://127.0.0.1:8092"
SIDECAR = "http://127.0.0.1:8100"
VECTOR_STORE_ID = "41e70e3d-cbbe-45a2-b185-9e8df3f8d7b5"  # openclaw-docs (DB openclaw_pgvector)
EMBED_MODEL = "qwen3-embedding"  # Qwen3-Embedding-0.6B 1024D, port 8084 via proxy
CHUNK_MAX_TOKENS = 512
DEFAULT_INBOX = pathlib.Path.home() / "openclaw" / "rag-documents"
SUPPORTED = {".pdf", ".docx", ".pptx", ".xlsx", ".md", ".html", ".htm", ".txt",
             ".png", ".jpg", ".jpeg", ".tiff", ".webp", ".csv", ".adoc"}


def keychain(service: str) -> str:
    return subprocess.check_output(
        ["security", "find-generic-password", "-s", service, "-w"]
    ).decode().strip()


def http_json(url: str, payload: dict | None = None, token: str | None = None,
              method: str = "POST", timeout: int = 120) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def docling_chunks(path: pathlib.Path) -> list[dict]:
    """Soumet le fichier au chunker hybride Docling (async) et retourne les chunks."""
    boundary = "----openclawragingest"
    body = b""
    fields = {"convert_ocr_engine": "ocrmac", "chunking_max_tokens": str(CHUNK_MAX_TOKENS)}
    for k, v in fields.items():
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode()
    body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; "
             f"filename=\"{path.name}\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode()
    body += path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{DOCLING}/v1/chunk/hybrid/file/async", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        task_id = json.loads(resp.read())["task_id"]

    deadline = time.time() + 600  # OCR de gros PDF peut etre long
    while time.time() < deadline:
        status = http_json(f"{DOCLING}/v1/status/poll/{task_id}", method="GET")["task_status"]
        if status == "success":
            return http_json(f"{DOCLING}/v1/result/{task_id}", method="GET")["chunks"]
        if status == "failure":
            raise RuntimeError(f"Docling a echoue sur {path.name} (task {task_id}) — voir logs/docling.error.log")
        time.sleep(3)
    raise TimeoutError(f"Docling timeout sur {path.name}")


def embed(texts: list[str], master: str) -> list[list[float]]:
    out = http_json(f"{PROXY}/v1/embeddings",
                    {"model": EMBED_MODEL, "input": texts}, token=master, timeout=300)
    # l'API peut reordonner: se fier au champ index
    by_index = sorted(out["data"], key=lambda d: d["index"])
    return [d["embedding"] for d in by_index]


def ingest_file(path: pathlib.Path, master: str, pgvk: str) -> int:
    chunks = docling_chunks(path)
    if not chunks:
        print(f"  ! aucun chunk pour {path.name}")
        return 0
    total = 0
    BATCH = 16  # aligne sur la batch size embedding MLX recommandee
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i:i + BATCH]
        vectors = embed([c["text"] for c in batch], master)
        payload = {"embeddings": [
            {
                "content": c["text"],
                "embedding": v,
                "metadata": {
                    "source": path.name,
                    "chunk_index": c["chunk_index"],
                    "headings": c.get("headings") or [],
                    "pages": c.get("page_numbers") or [],
                    "num_tokens": c.get("num_tokens"),
                },
            }
            for c, v in zip(batch, vectors)
        ]}
        http_json(f"{SIDECAR}/v1/vector_stores/{VECTOR_STORE_ID}/embeddings/batch",
                  payload, token=pgvk)
        total += len(batch)
    print(f"  + {path.name}: {total} chunks indexes")
    return total


def search(query: str, pgvk: str, top_k: int = 5) -> None:
    out = http_json(f"{SIDECAR}/v1/vector_stores/{VECTOR_STORE_ID}/search",
                    {"query": query, "max_num_results": top_k}, token=pgvk)
    for r in out.get("data", []):
        text = " ".join(c["text"] for c in r["content"])[:160]
        print(f"  score={r['score']:.3f}  [{r.get('filename', '?')}]  {text}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="*", help="fichiers ou dossiers (defaut: ~/openclaw/rag-documents)")
    ap.add_argument("--query", help="recherche smoke-test au lieu d'ingerer")
    args = ap.parse_args()

    pgvk = keychain("litellm-pgvector-api-key")
    if args.query:
        search(args.query, pgvk)
        return 0

    master = keychain("litellm-master-key")
    roots = [pathlib.Path(p).expanduser() for p in args.paths] or [DEFAULT_INBOX]
    files: list[pathlib.Path] = []
    for root in roots:
        if root.is_dir():
            files += sorted(p for p in root.rglob("*")
                            if p.is_file() and p.suffix.lower() in SUPPORTED)
        elif root.is_file():
            files.append(root)
        else:
            print(f"  ! introuvable: {root}")
    if not files:
        print(f"Aucun document a ingerer (depose tes fichiers dans {DEFAULT_INBOX})")
        return 1

    total = 0
    for f in files:
        try:
            total += ingest_file(f, master, pgvk)
        except Exception as exc:  # un doc en echec ne bloque pas le lot
            print(f"  ! echec {f.name}: {exc}", file=sys.stderr)
    print(f"Termine: {total} chunks dans openclaw-docs ({len(files)} fichiers traites)")
    return 0 if total else 1


if __name__ == "__main__":
    sys.exit(main())
