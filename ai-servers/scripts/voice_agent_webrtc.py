#!/usr/bin/env python3
"""Front WebRTC de l'agent vocal — FastRTC, port 8024 (UI Gradio).

Reconstruction 2026-07-08 du POC validé 2026-06-18 (l'original vivait gitignoré
dans ~/apple_all/voxcpm/pipeline/voxcpm2-lora/ et a été perdu avec l'effacement
du dossier le 2026-07-05 — cf. ~/apple_all/.cursor/rules/voice-agent.mdc).
Cette fois le fichier vit dans ~/ai-servers/scripts/ (sous git).

Conversation mains libres realtime : http://127.0.0.1:8024
  micro WebRTC → VAD Silero (fin de phrase auto) → Whisper FT voix Michael (:2022)
  → Gemma 4 omni (:8089, SSE) → VoxCPM2 v7 voix Michael (:8025, TTS par phrase
  pendant la génération) → audio streamé WebRTC. **Barge-in** : parler pendant
  la réponse l'interrompt (can_interrupt).

Différences vs le POC 2026-06-18 (serveurs dédiés :8023/:8026/:8027 retirés) :
  - branché sur les serveurs CANONIQUES du registre (whisper-stt :2022 LoRA v3,
    mlx-vlm-omni :8089 APC+MTP, voxcpm-tts :8025 timesteps=6) — pas d'instances
    dédiées ni de serveur métriques ;
  - chemin STT→texte (au lieu de gemma audio-native) : historique texte =
    prefix caching APC efficace multi-tours ; :8089 reste audio-capable si
    on veut y revenir ;
  - sans tools (le tool-loop ~30 outils reste dans Hammerspoon ⌥⌘ç).

Lancé par ~/ai-servers/launchers/voice-agent-webrtc.sh (venv fastrtc 0.0.34).
"""

from __future__ import annotations

import io
import json
import os
import re
import time
import wave
from datetime import date
from typing import Iterator, Optional

import gradio as gr
import httpx
import numpy as np
from fastrtc import AdditionalOutputs, ReplyOnPause, Stream

WHISPER_URL = os.environ.get("VOICE_WHISPER_URL", "http://127.0.0.1:2022/v1/audio/transcriptions")
LLM_URL = os.environ.get("VOICE_LLM_URL", "http://127.0.0.1:8089/v1/chat/completions")
LLM_MODEL = os.environ.get("VOICE_LLM_MODEL", "mlx-community/gemma-4-12B-it-8bit")
TTS_URL = os.environ.get("VOICE_TTS_URL", "http://127.0.0.1:8025/v1/audio/speech")
TTS_MODEL = os.environ.get("VOICE_TTS_MODEL", "michael-v7-mlx-8bit")
HOST = os.environ.get("VOICE_WEBRTC_HOST", "127.0.0.1")
PORT = int(os.environ.get("VOICE_WEBRTC_PORT", "8024"))

MAX_TOKENS = 1024
TEMPERATURE = 0.3
MAX_TURNS = 10       # tours user+assistant conservés
MEMORY_TTL = 600.0   # secondes — même politique que Hammerspoon ⌥⌘ç
OUTPUT_SR = 48000    # VoxCPM v7 sort du 48 kHz (mesuré 2026-07-08)

SYSTEM_PROMPT = f"""DATE: {date.today().isoformat()}. Tu es l'assistant VOCAL de Michael Ahern (pharmacien GMF, Abitibi). Conversation orale en temps réel : ta réponse est lue à voix haute par synthèse vocale.

RÈGLES DE SORTIE VOCALE :
1. Réponse COURTE et parlable : phrases simples, pas de markdown, pas de listes à puces, pas de code.
2. Chiffres et abréviations écrits pour l'oreille quand pertinent.
3. Français québécois naturel, termes techniques en anglais.
4. Signale l'incertitude — ne jamais combler un trou par de la confiance."""

# Même découpe/fusion que voxcpm_server_mlx.py : la ponctuation pilote la
# prosodie ; une phrase trop courte (sauf la 1re) fusionne avec la suivante.
_SENTENCE_RE = re.compile(r"[^.!?…]+[.!?…]+[\"»”']?\s*")
_MIN_CHARS = 25

_client = httpx.Client(timeout=300.0)

# Mono-usager (concurrency_limit=1) : mémoire de conversation globale + TTL.
_history: list[dict] = []
_last_turn_ts = 0.0


def _pcm_to_wav_bytes(audio: tuple[int, np.ndarray]) -> bytes:
    """WAV PCM propre pour Whisper — audio_to_bytes (fastrtc) encode en mp3
    et provoquait des hallucinations (« Sous-titrage ST' 501 », test 2026-07-08)."""
    sr, pcm = audio
    pcm = np.asarray(pcm)
    if pcm.ndim > 1:  # (channels, N) → mono
        pcm = pcm.mean(axis=0)
    if pcm.dtype != np.int16:
        pcm = (np.clip(pcm, -1.0, 1.0) * 32767.0).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


def _transcribe(audio: tuple[int, np.ndarray]) -> str:
    resp = _client.post(
        WHISPER_URL,
        files={"file": ("voice.wav", _pcm_to_wav_bytes(audio), "audio/wav")},
        data={"language": "fr", "response_format": "json"},
    )
    resp.raise_for_status()
    return (resp.json().get("text") or "").strip()


def _tts_sentence(sentence: str) -> Optional[tuple[int, np.ndarray]]:
    resp = _client.post(TTS_URL, json={"model": TTS_MODEL, "input": sentence, "stream": False})
    if resp.status_code >= 400:
        return None
    with wave.open(io.BytesIO(resp.content), "rb") as wf:
        sr = wf.getframerate()
        pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
    if sr != OUTPUT_SR:  # garde-fou pitch si le ckpt TTS change de sample rate
        x = np.linspace(0.0, 1.0, num=round(len(pcm) * OUTPUT_SR / sr), endpoint=False)
        pcm = np.interp(x, np.linspace(0.0, 1.0, num=len(pcm), endpoint=False), pcm).astype(np.int16)
    return OUTPUT_SR, pcm


def _stream_llm(messages: list[dict]) -> Iterator[str]:
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE,
        "stream": True,
    }
    with _client.stream("POST", LLM_URL, json=payload) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data.strip() == "[DONE]":
                break
            delta = (json.loads(data).get("choices") or [{}])[0].get("delta") or {}
            if delta.get("content"):
                yield delta["content"]


def _pop_sentences(buffer: str, first_done: bool) -> tuple[list[str], str]:
    """Extrait les phrases complètes ; la 1re part tout de suite (TTFA minimal),
    ensuite on attend _MIN_CHARS pour éviter les artefacts d'amorce VoxCPM."""
    sentences: list[str] = []
    pos = 0
    for m in _SENTENCE_RE.finditer(buffer):
        if m.start() != pos:
            break
        candidate = m.group(0).strip()
        if not first_done or len(candidate) >= _MIN_CHARS or not sentences:
            sentences.append(candidate)
        else:
            sentences[-1] = f"{sentences[-1]} {candidate}"
        pos = m.end()
        first_done = True
    return sentences, buffer[pos:]


def voice_reply(audio: tuple[int, np.ndarray]):
    """Handler ReplyOnPause : tour de parole → texte → LLM streamé → TTS par
    phrase, yield audio au fil de l'eau (barge-in géré par FastRTC)."""
    global _history, _last_turn_ts

    if time.monotonic() - _last_turn_ts > MEMORY_TTL:
        _history = []

    try:
        text = _transcribe(audio)
    except httpx.HTTPError as exc:
        print(f"[voice-agent-webrtc] whisper :2022 injoignable: {exc}")
        return
    if not text:
        return

    _history = (_history + [{"role": "user", "content": text}])[-MAX_TURNS * 2:]
    yield AdditionalOutputs(list(_history))

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + _history
    answer, buffer, first_done = "", "", False
    try:
        for delta in _stream_llm(messages):
            answer += delta
            buffer += delta
            sentences, buffer = _pop_sentences(buffer, first_done)
            for sentence in sentences:
                first_done = True
                chunk = _tts_sentence(sentence)
                if chunk:
                    yield chunk
    except httpx.HTTPError as exc:
        print(f"[voice-agent-webrtc] LLM :8089 erreur: {exc}")
        return
    finally:
        # Sauve le tour même interrompu (barge-in) — GeneratorExit passe ici.
        if answer:
            _history = (_history + [{"role": "assistant", "content": answer}])[-MAX_TURNS * 2:]
            _last_turn_ts = time.monotonic()

    rest = buffer.strip()
    if rest:
        chunk = _tts_sentence(rest)
        if chunk:
            yield chunk
    yield AdditionalOutputs(list(_history))


chatbot = gr.Chatbot(type="messages", label="Conversation", height=380)

stream = Stream(
    ReplyOnPause(voice_reply, can_interrupt=True, output_sample_rate=OUTPUT_SR),
    modality="audio",
    mode="send-receive",
    concurrency_limit=1,
    additional_outputs=[chatbot],
    additional_outputs_handler=lambda old, new: new,
    ui_args={
        "title": "🎙️ Agent vocal — Whisper FT → Gemma 4 → VoxCPM2 (voix Michael)",
    },
)

if __name__ == "__main__":
    stream.ui.launch(server_name=HOST, server_port=PORT, quiet=True)
