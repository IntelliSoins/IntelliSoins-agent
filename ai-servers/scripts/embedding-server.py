#!/usr/bin/env python3
"""
OpenAI-compatible local embedding server for Qwen3-Embedding on Apple Silicon.

Endpoints:
  GET  /health
  GET  /v1/models
  POST /v1/embeddings
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from typing import Any

import numpy as np
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


DEFAULT_MODEL = "Qwen/Qwen3-Embedding-0.6B"
MODEL_ALIASES = {
    "",
    "qwen3-embedding",
    "Qwen3-Embedding-0.6B",
    "Qwen3-Embedding-8B",
    DEFAULT_MODEL,
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("embedding-server")

app = FastAPI(
    title="Local Embedding Server",
    description="OpenAI-compatible Qwen3 embedding service",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

embedding_model = None
embedding_model_name = DEFAULT_MODEL
embedding_dimension = 1024
device_name = "mps" if torch.backends.mps.is_available() else "cpu"


class EmbeddingRequest(BaseModel):
    input: str | list[str] = Field(..., description="Text or list of texts to embed")
    model: str = Field(default=DEFAULT_MODEL, description="Embedding model name")
    dimensions: int | None = Field(default=None, ge=1, le=1024)
    normalize: bool = True


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "local"


def load_model(model_id: str = DEFAULT_MODEL):
    global embedding_model, embedding_model_name, embedding_dimension

    if embedding_model is not None and embedding_model_name == model_id:
        return embedding_model

    logger.info("Loading embedding model: %s on %s", model_id, device_name)
    start = time.monotonic()

    try:
        from sentence_transformers import SentenceTransformer

        embedding_model = SentenceTransformer(
            model_id,
            device=device_name,
            trust_remote_code=True,
        )
        embedding_model_name = model_id
        dimension = embedding_model.get_sentence_embedding_dimension()
        if dimension:
            embedding_dimension = int(dimension)
    except Exception:
        logger.exception("Failed to load embedding model")
        raise

    logger.info(
        "Embedding model loaded in %.2fs, dimension=%s",
        time.monotonic() - start,
        embedding_dimension,
    )
    return embedding_model


def resolve_model_id(model_id: str) -> str:
    if model_id in MODEL_ALIASES:
        return DEFAULT_MODEL
    return model_id


@app.on_event("startup")
async def startup_event():
    load_model(embedding_model_name)


@app.get("/health")
async def health():
    return {
        "status": "ok" if embedding_model is not None else "loading",
        "model_loaded": embedding_model is not None,
        "model": embedding_model_name,
        "dimension": embedding_dimension,
        "device": device_name,
    }


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            ModelInfo(id=DEFAULT_MODEL).model_dump(),
            ModelInfo(id="Qwen3-Embedding-8B").model_dump(),
            ModelInfo(id="qwen3-embedding").model_dump(),
        ],
    }


@app.post("/v1/embeddings")
async def embeddings(request: EmbeddingRequest):
    texts = [request.input] if isinstance(request.input, str) else request.input
    if not texts:
        raise HTTPException(status_code=400, detail="input must not be empty")
    if any(not isinstance(text, str) or text == "" for text in texts):
        raise HTTPException(status_code=400, detail="all input values must be non-empty strings")

    try:
        model = load_model(resolve_model_id(request.model))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    start = time.monotonic()

    def encode() -> np.ndarray:
        encoded = model.encode(
            texts,
            normalize_embeddings=request.normalize,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        if request.dimensions is not None:
            encoded = encoded[:, : request.dimensions]
            if request.normalize:
                norms = np.linalg.norm(encoded, axis=1, keepdims=True)
                encoded = encoded / np.where(norms == 0, 1, norms)
        return encoded.astype(float)

    loop = asyncio.get_running_loop()
    vectors = await loop.run_in_executor(None, encode)

    elapsed_ms = int((time.monotonic() - start) * 1000)
    logger.info("Embedded %s text(s) in %sms", len(texts), elapsed_ms)

    data: list[dict[str, Any]] = [
        {
            "object": "embedding",
            "index": index,
            "embedding": vector.tolist(),
        }
        for index, vector in enumerate(vectors)
    ]
    prompt_tokens = sum(max(1, len(text) // 4) for text in texts)

    return {
        "object": "list",
        "data": data,
        "model": embedding_model_name,
        "usage": {
            "prompt_tokens": prompt_tokens,
            "total_tokens": prompt_tokens,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Local OpenAI-compatible embedding server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8084)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    global embedding_model_name
    embedding_model_name = args.model

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
