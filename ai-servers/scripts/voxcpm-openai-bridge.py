#!/usr/bin/env python3
"""
OpenAI-compatible bridge for local VoxCPM TTS backends.

Supports:
  - mlx-audio.server (:8025/v1/audio/speech)
  - voxcpm_server_mlx.py (:8025/tts)
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

DEFAULT_BACKEND = os.environ.get("VOXCPM_BACKEND_URL", "http://127.0.0.1:8025")
DEFAULT_MODEL = os.environ.get(
    "VOXCPM_MODEL",
    "/Users/michaelahern/apple_all/voxcpm/pipeline/voxcpm2-lora/checkpoints-merged-michael-v7-mlx-8bit",
)
MODEL_ALIASES = {
    "": DEFAULT_MODEL,
    "michael": DEFAULT_MODEL,
    "michael-v7-mlx-8bit": DEFAULT_MODEL,
    # alias legacy (clients OpenClaw configurés avant la perte du v6)
    "michael-v6-mlx-8bit": DEFAULT_MODEL,
}

# Référence vocale (clonage) : le LoRA v7 capte le timbre, mais VoxCPM2 rend la
# prosodie beaucoup plus réaliste avec un extrait de la vraie voix en ref_audio
# + sa transcription exacte en ref_text (constat v3-v6, rule apple_all voxcpm.md).
DEFAULT_REF_AUDIO = os.environ.get(
    "VOXCPM_REF_AUDIO",
    "/Users/michaelahern/apple_all/voxcpm/pipeline/voxcpm2-lora/ref-voice-michael/ref-voice-michael.wav",
)
_ref_text_file = os.environ.get(
    "VOXCPM_REF_TEXT_FILE",
    "/Users/michaelahern/apple_all/voxcpm/pipeline/voxcpm2-lora/ref-voice-michael/ref-voice-michael.txt",
)


def _load_ref_text(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip() or None
    except OSError:
        return None


DEFAULT_REF_TEXT = os.environ.get("VOXCPM_REF_TEXT") or _load_ref_text(_ref_text_file)


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
    # stream=true : propagé au backend voxcpm_server_mlx (streaming par phrases,
    # TTFA ~0.5 s au lieu d'attendre toute la génération) — agent vocal realtime.
    stream: bool = False
    ref_audio: str | None = None
    ref_text: str | None = None


app = FastAPI(title="VoxCPM OpenAI bridge", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

backend_url = DEFAULT_BACKEND
# Client persistant : évite le handshake TCP/TLS par requête et porte les
# réponses streamées (fermées via BackgroundTask après envoi complet).
_client = httpx.AsyncClient(timeout=300.0)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "backend": backend_url}


@app.get("/v1/models")
async def models() -> dict[str, object]:
    return {
        "object": "list",
        "data": [{"id": "michael-v7-mlx-8bit", "object": "model", "owned_by": "local"}],
    }


def _openai_payload(req: SpeechRequest) -> dict:
    model = resolve_model(req.model)
    payload = {
        "model": model,
        "input": req.input,
        "response_format": req.response_format or "wav",
        "stream": req.stream,
    }
    if req.voice:
        payload["voice"] = req.voice
    if req.speed is not None:
        payload["speed"] = req.speed

    # Injection de la référence voix Michael pour le modèle fine-tuné :
    # les clients (Hammerspoon ⌥v, OpenClaw) n'envoient que model+input.
    ref_audio = req.ref_audio
    ref_text = req.ref_text
    if not ref_audio and model == DEFAULT_MODEL and os.path.exists(DEFAULT_REF_AUDIO):
        ref_audio = DEFAULT_REF_AUDIO
        ref_text = ref_text or DEFAULT_REF_TEXT
    if ref_audio:
        payload["ref_audio"] = ref_audio
        if ref_text:
            payload["ref_text"] = ref_text
    return payload


async def _openai_backend(req: SpeechRequest) -> httpx.Response:
    request = _client.build_request(
        "POST",
        f"{backend_url.rstrip('/')}/v1/audio/speech",
        json=_openai_payload(req),
    )
    # stream=True : les octets partent vers le client dès la première phrase
    # générée par le backend (TTFA) au lieu d'être bufferisés ici.
    return await _client.send(request, stream=req.stream)


async def _native_backend(req: SpeechRequest) -> httpx.Response:
    payload = {"text": req.input}
    if req.speed is not None:
        payload["speed"] = req.speed
    return await _client.post(f"{backend_url.rstrip('/')}/tts", json=payload)


@app.post("/v1/audio/speech")
async def speech(req: SpeechRequest) -> Response:
    try:
        response = await _openai_backend(req)
        if response.status_code == 404:
            # backend natif legacy (mlx_audio.server) : pas de streaming
            await response.aclose()
            response = await _native_backend(req)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"VoxCPM backend unreachable: {exc}") from exc

    media_type = "audio/wav" if (req.response_format or "wav") == "wav" else "audio/mpeg"

    if response.status_code >= 400:
        body = await response.aread()  # ok même si déjà lu (contenu caché)
        await response.aclose()
        raise HTTPException(status_code=response.status_code, detail=body.decode(errors="replace"))

    if req.stream and not response.is_closed:
        return StreamingResponse(
            response.aiter_bytes(),
            media_type=media_type,
            background=BackgroundTask(response.aclose),
        )
    return Response(content=response.content, media_type=media_type)


def main() -> None:
    parser = argparse.ArgumentParser(description="VoxCPM OpenAI bridge")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8883)
    parser.add_argument("--backend", default=DEFAULT_BACKEND)
    args = parser.parse_args()

    global backend_url
    backend_url = args.backend.rstrip("/")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
