#!/usr/bin/env python3
"""
OpenAI-compatible bridge for Spark VoxCPM TTS (Nano-vLLM-VoxCPM).

Traduit /v1/audio/speech (OpenAI) → /generate (Nano-vLLM natif).
Backends : sparklan http://10.0.1.1:8026 primaire (~4 ms maison) puis mesh
http://10.0.0.5:8026 fallback (~82 ms hub VPS). Consommé par Hammerspoon ⌥v
(init.lua), l'agent vocal (voice-agent-webrtc.sh) et LiteLLM :8092 (spark-voxcpm-v8).
"""

from __future__ import annotations

import argparse
import os

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse

# Backends : sparklan primaire (~4 ms maison, tunnel WG direct LAN) puis mesh
# fallback (~82 ms hub VPS hors maison). Même pattern que whisper/nllb dans
# Hammerspoon init.lua — le bridge sert un seul endpoint OpenAI (:8884) aux
# clients (Hammerspoon ⌥v, agent vocal, LiteLLM) et gère le failover ici.
SPARKLAN_BACKEND = os.environ.get("SPARK_VOXCPM_BACKEND_SPARKLAN", "http://10.0.1.1:8026")
MESH_BACKEND = os.environ.get("SPARK_VOXCPM_BACKEND_MESH", "http://10.0.0.5:8026")
BACKEND_URLS = [SPARKLAN_BACKEND, MESH_BACKEND]
DEFAULT_MODEL = os.environ.get("SPARK_VOXCPM_MODEL", "michael-v8")
MODEL_ALIASES = {
    "": DEFAULT_MODEL,
    "michael": DEFAULT_MODEL,
    "michael-v8": DEFAULT_MODEL,
    "spark-voxcpm-v8": DEFAULT_MODEL,
}


def resolve_model(model: str | None) -> str:
    if not model:
        return DEFAULT_MODEL
    return MODEL_ALIASES.get(model, model)


class SpeechRequest(BaseModel):
    model: str = Field(default=DEFAULT_MODEL)
    input: str
    voice: str | None = None
    response_format: str | None = "wav"
    speed: float | None = None
    stream: bool = False


app = FastAPI(title="Spark VoxCPM OpenAI bridge", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect timeout court (3 s) sur la 1re tentative sparklan : si le tunnel LAN
# est down (hors maison), on bascule vite sur mesh au lieu d'attendre 300 s.
_client = httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=3.0))
_active_backend = SPARKLAN_BACKEND


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "backend": _active_backend,
            "sparklan": SPARKLAN_BACKEND, "mesh": MESH_BACKEND}


@app.get("/v1/models")
async def models() -> dict[str, object]:
    return {
        "object": "list",
        "data": [{"id": "spark-voxcpm-v8", "object": "model", "owned_by": "spark-dgx"}],
    }


def _nanovllm_payload(req: SpeechRequest) -> dict:
    model = resolve_model(req.model)
    payload = {
        "target_text": req.input,
        "lora_name": model,
        "cfg_value": 2.0,
        "inference_timesteps": 10,
        "response_format": req.response_format or "wav",
    }
    return payload


async def _nanovllm_backend(req: SpeechRequest) -> httpx.Response:
    """Tente sparklan (rapide) puis mesh (fallback) — ConnectError/ConnectTimeout
    sur sparklan déclenche le retry mesh. Une fois connecté, on ne bascule plus
    (une 4xx/5xx est une vraie erreur backend, pas un problème réseau)."""
    global _active_backend
    last_exc: Exception | None = None
    for url in BACKEND_URLS:
        try:
            request = _client.build_request(
                "POST",
                f"{url.rstrip('/')}/generate",
                json=_nanovllm_payload(req),
            )
            response = await _client.send(request, stream=req.stream)
            _active_backend = url
            return response
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            last_exc = exc
            continue
    raise last_exc  # type: ignore[misc]


@app.post("/v1/audio/speech", response_model=None)
async def speech(req: SpeechRequest) -> Response:
    try:
        response = await _nanovllm_backend(req)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Spark VoxCPM backend unreachable (sparklan + mesh): {exc}") from exc

    media_type = "audio/wav" if (req.response_format or "wav") == "wav" else "audio/mpeg"

    if response.status_code >= 400:
        body = await response.aread()
        await response.aclose()
        raise HTTPException(status_code=response.status_code, detail=body.decode(errors="replace"))

    if req.stream and not response.is_closed:
        return StreamingResponse(
            response.aiter_bytes(),
            media_type=media_type,
            background=BackgroundTask(response.aclose),
        )
    
    content = await response.aread()
    await response.aclose()
    # Filtrer les headers hop-by-hop / framing : la réponse est bufférisée (content=
    # fixe) → Starlette pose son propre Content-Length. Si on forward le
    # Transfer-Encoding: chunked du backend Nano-vLLM, on émet les DEUX → violation
    # RFC 7230 §3.3.2 → l'OpenAI SDK derrière LiteLLM rejette (400 → 500 au proxy).
    hop_by_hop = {"transfer-encoding", "content-length", "connection", "keep-alive",
                  "content-encoding", "te", "trailers", "upgrade"}
    fwd = {k: v for k, v in response.headers.items() if k.lower() not in hop_by_hop}
    return Response(content=content, media_type=media_type, headers=fwd)


def main() -> None:
    parser = argparse.ArgumentParser(description="Spark VoxCPM OpenAI bridge")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8884)
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
