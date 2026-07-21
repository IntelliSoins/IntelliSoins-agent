#!/usr/bin/env python3
"""
OpenAI-compatible bridge for Spark VoxCPM TTS (Nano-vLLM-VoxCPM).

Traduit /v1/audio/speech (OpenAI) → /generate (Nano-vLLM natif).
Backends : sparklan http://10.0.1.1:8026 primaire (~4 ms maison) puis mesh
http://10.0.0.5:8026 fallback (~82 ms hub VPS). Consommé par Hammerspoon ⌥v
(init.lua), l'agent vocal (voice-agent-webrtc.sh) et LiteLLM :8092 (spark-voxcpm-v8).

Qualité (2026-07-17) : style parenthétique OpenBMB, CFG 2.0, timesteps 10,
segmentation des longs textes — voir plan Améliorer VoxCPM LoRA v8.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import wave

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
# Qualité > latence (2026-07-17) : défauts officiels OpenBMB CFG=2.0 / timesteps=10.
# Timesteps effectifs = VOXCPM_INFERENCE_TIMESTEPS côté Spark (nano-vllm 2.0.2).
DEFAULT_CFG = float(os.environ.get("SPARK_VOXCPM_CFG", "2.2"))
DEFAULT_TIMESTEPS = int(os.environ.get("SPARK_VOXCPM_TIMESTEPS", "10"))
# Hi-Fi (prod) : laisser vide. Controllable Cloning seulement :
# SPARK_VOXCPM_STYLE_PREFIX='(slightly faster, clear enunciation) '
STYLE_PREFIX = os.environ.get("SPARK_VOXCPM_STYLE_PREFIX", "")
# Segmenter au-delà de N caractères (1–2 phrases) pour éviter buzz / runaway.
SEGMENT_CHARS = int(os.environ.get("SPARK_VOXCPM_SEGMENT_CHARS", "180"))
MODEL_ALIASES = {
    "": DEFAULT_MODEL,
    "michael": DEFAULT_MODEL,
    "michael-v8": DEFAULT_MODEL,  # prod = v10 weights
    "michael-v9": "michael-v9",
    "michael-v10": "michael-v10",
    "spark-voxcpm-v8": DEFAULT_MODEL,
    "spark-voxcpm-v9": "michael-v9",
    "spark-voxcpm-v10": "michael-v10",
    "michael-v8-final": "michael-v8-final",
    "michael-v8-s500": "michael-v8-s500",
    "michael-v8-s250": "michael-v8-s250",
}


def resolve_model(model: str | None) -> str:
    if not model:
        return DEFAULT_MODEL
    return MODEL_ALIASES.get(model, model)


def apply_style(text: str) -> str:
    """Préfixe style OpenBMB si absent (évite double-préfixe)."""
    t = (text or "").strip()
    if not t or not STYLE_PREFIX:
        return t
    if t.startswith("("):
        return t
    return STYLE_PREFIX + t


def split_segments(text: str) -> list[str]:
    """Découpe en phrases courtes pour la prosodie / stabilité long-form."""
    t = (text or "").strip()
    if not t or len(t) <= SEGMENT_CHARS:
        return [t] if t else []
    parts = re.split(r"(?<=[.!?…])\s+", t)
    segments: list[str] = []
    buf = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        candidate = f"{buf} {part}".strip() if buf else part
        if len(candidate) <= SEGMENT_CHARS:
            buf = candidate
        else:
            if buf:
                segments.append(buf)
            buf = part
    if buf:
        segments.append(buf)
    return segments or [t]


def _wav_pcm(data: bytes) -> tuple[int, int, bytes]:
    """Retourne (nchannels, framerate, pcm_frames) depuis un WAV."""
    with wave.open(io.BytesIO(data), "rb") as wf:
        return wf.getnchannels(), wf.getframerate(), wf.readframes(wf.getnframes())


def concat_wavs(blobs: list[bytes]) -> bytes:
    if not blobs:
        raise ValueError("no wav blobs")
    if len(blobs) == 1:
        return blobs[0]
    nch, rate, pcm = _wav_pcm(blobs[0])
    frames = [pcm]
    for blob in blobs[1:]:
        c, r, p = _wav_pcm(blob)
        if c != nch or r != rate:
            raise ValueError(f"wav mismatch: {c}/{r} vs {nch}/{rate}")
        frames.append(p)
    out = io.BytesIO()
    with wave.open(out, "wb") as wf:
        wf.setnchannels(nch)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"".join(frames))
    return out.getvalue()


class SpeechRequest(BaseModel):
    model: str = Field(default=DEFAULT_MODEL)
    input: str
    voice: str | None = None
    response_format: str | None = "wav"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: float = Field(default=0.0, ge=-12.0, le=12.0)
    cfg_value: float | None = Field(default=None, ge=0.0, le=10.0)
    temperature: float = Field(default=1.0, gt=0.0, le=2.0)
    inference_timesteps: int | None = None
    clone_mode: str | None = None
    style: str | None = None
    emotion: str | None = None
    tone: str | None = None
    stream: bool = False
    # Optional overrides; Spark server applies /models/ref defaults when omitted
    # (Mac paths must NOT be injected — they are not visible inside the container).
    ref_audio: str | None = None
    ref_text: str | None = None
    prompt_wav: str | None = None
    prompt_text: str | None = None
    seed: int | None = None


app = FastAPI(title="Spark VoxCPM OpenAI bridge", version="1.1.0")
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
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "backend": _active_backend,
        "sparklan": SPARKLAN_BACKEND,
        "mesh": MESH_BACKEND,
        "cfg": DEFAULT_CFG,
        "timesteps": DEFAULT_TIMESTEPS,
        "style_prefix": STYLE_PREFIX,
        "segment_chars": SEGMENT_CHARS,
        "model": DEFAULT_MODEL,
        "ref_policy": "spark-server-default",
        "controls": {
            "clone_modes": ["auto", "hifi", "controllable", "none"],
            "style": True,
            "emotion": True,
            "tone": True,
            "speed": [0.5, 2.0],
            "pitch_semitones": [-12.0, 12.0],
            "temperature": [0.0, 2.0],
            "cfg_value": [0.0, 10.0],
        },
    }


@app.get("/v1/models")
async def models() -> dict[str, object]:
    return {
        "object": "list",
        "data": [
            {"id": "spark-voxcpm-v8", "object": "model", "owned_by": "spark-dgx"},
            {"id": DEFAULT_MODEL, "object": "model", "owned_by": "spark-dgx"},
            {"id": "michael-v9", "object": "model", "owned_by": "spark-dgx"},
            {"id": "michael-v10", "object": "model", "owned_by": "spark-dgx"},
            {"id": "michael-v8-final", "object": "model", "owned_by": "spark-dgx"},
            {"id": "michael-v8-s500", "object": "model", "owned_by": "spark-dgx"},
            {"id": "michael-v8-s250", "object": "model", "owned_by": "spark-dgx"},
            {"id": "base", "object": "model", "owned_by": "spark-dgx"},
        ],
    }


def _nanovllm_payload(req: SpeechRequest, text: str) -> dict:
    model = resolve_model(req.model)
    payload: dict = {
        "target_text": text,
        "lora_name": resolve_model(req.voice) if req.voice else model,
        "cfg_value": DEFAULT_CFG if req.cfg_value is None else req.cfg_value,
        "inference_timesteps": DEFAULT_TIMESTEPS if req.inference_timesteps is None else req.inference_timesteps,
        "temperature": req.temperature,
        "speed": req.speed,
        "pitch": req.pitch,
        "response_format": req.response_format or "wav",
    }
    for name in ("clone_mode", "style", "emotion", "tone"):
        value = getattr(req, name)
        if value:
            payload[name] = value
    if req.seed is not None:
        payload["seed"] = req.seed
    ref_audio = req.ref_audio or req.prompt_wav
    ref_text = req.ref_text or req.prompt_text
    if ref_audio:
        payload["ref_audio"] = ref_audio
        if ref_text:
            payload["ref_text"] = ref_text
    elif ref_text:
        payload["ref_text"] = ref_text
    return payload


async def _post_generate(payload: dict, stream: bool) -> httpx.Response:
    """Tente sparklan puis mesh."""
    global _active_backend
    last_exc: Exception | None = None
    for url in BACKEND_URLS:
        try:
            request = _client.build_request(
                "POST",
                f"{url.rstrip('/')}/generate",
                json=payload,
            )
            response = await _client.send(request, stream=stream)
            _active_backend = url
            return response
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            last_exc = exc
            continue
    raise last_exc  # type: ignore[misc]


@app.post("/v1/audio/speech", response_model=None)
async def speech(req: SpeechRequest) -> Response:
    styled = apply_style(req.input)
    segments = split_segments(styled)
    # Style déjà sur le 1er segment ; les suivants reçoivent aussi le préfixe
    # (OpenBMB recommande le contrôle par utterance).
    texts = [apply_style(s) if i > 0 else s for i, s in enumerate(segments)]
    media_type = "audio/wav" if (req.response_format or "wav") == "wav" else "audio/mpeg"
    use_stream = bool(req.stream) and len(texts) == 1 and media_type == "audio/wav"

    try:
        if use_stream:
            response = await _post_generate(_nanovllm_payload(req, texts[0]), stream=True)
        else:
            # Multi-segments ou non-stream : buffériser + concat WAV
            blobs: list[bytes] = []
            meta_headers: dict[str, str] = {}
            for text in texts:
                response = await _post_generate(_nanovllm_payload(req, text), stream=False)
                if response.status_code >= 400:
                    body = await response.aread()
                    await response.aclose()
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=body.decode(errors="replace"),
                    )
                blob = await response.aread()
                await response.aclose()
                blobs.append(blob)
                meta_headers = {
                    k: v
                    for k, v in response.headers.items()
                    if k.lower().startswith("x-")
                }
            content = concat_wavs(blobs) if (req.response_format or "wav") == "wav" else b"".join(blobs)
            hop_by_hop = {
                "transfer-encoding",
                "content-length",
                "connection",
                "keep-alive",
                "content-encoding",
                "te",
                "trailers",
                "upgrade",
            }
            fwd = {k: v for k, v in meta_headers.items() if k.lower() not in hop_by_hop}
            fwd["X-Bridge-Segments"] = str(len(texts))
            return Response(content=content, media_type=media_type, headers=fwd)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Spark VoxCPM backend unreachable (sparklan + mesh): {exc}",
        ) from exc

    if response.status_code >= 400:
        body = await response.aread()
        await response.aclose()
        raise HTTPException(status_code=response.status_code, detail=body.decode(errors="replace"))

    if use_stream and not response.is_closed:
        return StreamingResponse(
            response.aiter_bytes(),
            media_type=media_type,
            background=BackgroundTask(response.aclose),
        )

    content = await response.aread()
    await response.aclose()
    hop_by_hop = {
        "transfer-encoding",
        "content-length",
        "connection",
        "keep-alive",
        "content-encoding",
        "te",
        "trailers",
        "upgrade",
    }
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
