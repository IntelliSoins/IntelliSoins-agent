#!/usr/bin/env python3
"""Frontend Gradio de l'agent vocal — port 7860.

Même pipeline realtime que l'agent vocal Hammerspoon (⌥⌘ç), en interface web :
  micro → Whisper FT voix Michael (:2022) → Gemma 4 omni (:8089, SSE streaming)
        → VoxCPM2 v7 voix Michael (:8025, TTS par phrase) → audio streamé (autoplay).

Optimisations realtime :
  - LLM streamé en SSE : le texte s'affiche au fil des tokens ;
  - pipeline LLM→TTS par phrases : dès qu'une phrase est complète, elle part en
    synthèse pendant que Gemma continue de générer → premier son en ~1-2 s au
    lieu d'attendre toute la réponse ;
  - TTS direct sur :8025 (référence vocale injectée côté serveur, timesteps=6).

Sans outils (le tool-loop ~30 outils reste dans Hammerspoon) ; mémoire de
conversation dans la session Gradio (bouton Effacer pour reset).

Lancé par ~/ai-servers/launchers/voice-agent-gradio.sh (venv fastrtc, gradio 5.50).
"""

from __future__ import annotations

import io
import json
import os
import re
import wave
from datetime import date
from typing import Iterator, Optional

import gradio as gr
import httpx
import numpy as np

WHISPER_URL = os.environ.get("VOICE_WHISPER_URL", "http://127.0.0.1:2022/v1/audio/transcriptions")
LLM_URL = os.environ.get("VOICE_LLM_URL", "http://127.0.0.1:8089/v1/chat/completions")
LLM_MODEL = os.environ.get("VOICE_LLM_MODEL", "mlx-community/gemma-4-12B-it-8bit")
TTS_URL = os.environ.get("VOICE_TTS_URL", "http://127.0.0.1:8025/v1/audio/speech")
TTS_MODEL = os.environ.get("VOICE_TTS_MODEL", "michael-v7-mlx-8bit")
HOST = os.environ.get("VOICE_GRADIO_HOST", "127.0.0.1")
PORT = int(os.environ.get("VOICE_GRADIO_PORT", "7860"))

MAX_TOKENS = 1024
TEMPERATURE = 0.3
MAX_TURNS = 10  # tours user+assistant conservés en mémoire de session

# Aligné sur VOICE_SYSTEM de ~/.hammerspoon/init.lua (sans la section outils).
SYSTEM_PROMPT = f"""DATE: {date.today().isoformat()}. Tu es l'assistant VOCAL de Michael Ahern (pharmacien GMF, Abitibi). Ta réponse sera lue à voix haute par synthèse vocale.

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


def transcribe(audio_path: str) -> str:
    with open(audio_path, "rb") as fh:
        resp = _client.post(
            WHISPER_URL,
            files={"file": (os.path.basename(audio_path), fh, "audio/wav")},
            data={"language": "fr", "response_format": "json"},
        )
    resp.raise_for_status()
    return (resp.json().get("text") or "").strip()


def _tts_sentence(sentence: str) -> Optional[tuple[int, np.ndarray]]:
    resp = _client.post(
        TTS_URL,
        json={"model": TTS_MODEL, "input": sentence, "stream": False},
    )
    if resp.status_code >= 400:
        return None
    with wave.open(io.BytesIO(resp.content), "rb") as wf:
        sample_rate = wf.getframerate()
        pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
    return sample_rate, pcm


def _stream_llm(messages: list[dict]) -> Iterator[str]:
    """Yield les deltas de contenu du chat completion SSE."""
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
            chunk = json.loads(data)
            delta = (chunk.get("choices") or [{}])[0].get("delta") or {}
            content = delta.get("content")
            if content:
                yield content


def _pop_sentences(buffer: str, first_done: bool) -> tuple[list[str], str]:
    """Extrait les phrases complètes du buffer ; garde le reste en cours."""
    sentences: list[str] = []
    pos = 0
    for m in _SENTENCE_RE.finditer(buffer):
        if m.start() != pos:
            break
        candidate = m.group(0).strip()
        # 1re phrase : part tout de suite (TTFA minimal) ; ensuite on attend
        # _MIN_CHARS pour éviter les artefacts d'amorce VoxCPM.
        if not first_done or len(candidate) >= _MIN_CHARS or not sentences:
            sentences.append(candidate)
        else:
            sentences[-1] = f"{sentences[-1]} {candidate}"
        pos = m.end()
        first_done = True
    return sentences, buffer[pos:]


def respond(history: list[dict]):
    """Générateur : streame (chatbot, chunk audio) au fil de Gemma + VoxCPM."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
    history = history + [{"role": "assistant", "content": ""}]

    buffer = ""
    first_done = False
    try:
        for delta in _stream_llm(messages):
            buffer += delta
            history[-1]["content"] += delta
            sentences, buffer = _pop_sentences(buffer, first_done)
            if not sentences:
                yield history, gr.skip()
                continue
            for sentence in sentences:
                first_done = True
                audio = _tts_sentence(sentence)
                yield history, audio if audio else gr.skip()
    except httpx.HTTPError as exc:
        history[-1]["content"] += f"\n[erreur LLM : {exc}]"
        yield history, gr.skip()
        return

    rest = buffer.strip()
    if rest:
        audio = _tts_sentence(rest)
        if audio:
            yield history, audio
    yield history, gr.skip()


def on_audio(audio_path: Optional[str], history: list[dict]):
    if not audio_path:
        yield history, gr.skip(), None
        return
    try:
        text = transcribe(audio_path)
    except httpx.HTTPError as exc:
        gr.Warning(f"Whisper :2022 injoignable — {exc}")
        yield history, gr.skip(), None
        return
    if not text:
        gr.Warning("Rien transcrit.")
        yield history, gr.skip(), None
        return
    history = (history + [{"role": "user", "content": text}])[-MAX_TURNS * 2:]
    yield history, gr.skip(), None
    for h, audio in respond(history):
        yield h, audio, None


def on_text(text: str, history: list[dict]):
    text = (text or "").strip()
    if not text:
        yield history, gr.skip(), ""
        return
    history = (history + [{"role": "user", "content": text}])[-MAX_TURNS * 2:]
    yield history, gr.skip(), ""
    for h, audio in respond(history):
        yield h, audio, ""


with gr.Blocks(title="Agent vocal — Michael") as demo:
    gr.Markdown("## 🎙️ Agent vocal local — Whisper FT → Gemma 4 → VoxCPM2 (voix Michael)")
    chatbot = gr.Chatbot(type="messages", height=420, label="Conversation")
    tts_out = gr.Audio(
        streaming=True, autoplay=True, visible=True, label="Voix Michael (streaming)"
    )
    with gr.Row():
        mic = gr.Audio(sources=["microphone"], type="filepath", label="Parle (l'envoi part à l'arrêt)")
        txt = gr.Textbox(label="… ou écris", placeholder="Question…", scale=2)
    clear = gr.Button("🔄 Nouvelle conversation")

    mic.stop_recording(on_audio, [mic, chatbot], [chatbot, tts_out, mic])
    txt.submit(on_text, [txt, chatbot], [chatbot, tts_out, txt])
    clear.click(lambda: ([], None, ""), None, [chatbot, tts_out, txt])

if __name__ == "__main__":
    demo.launch(server_name=HOST, server_port=PORT, show_api=False, quiet=True)
