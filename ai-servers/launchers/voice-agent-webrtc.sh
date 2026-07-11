#!/bin/bash
# Agent vocal — front WebRTC FastRTC (UI Gradio), port 8024
# micro WebRTC + VAD Silero + barge-in → Whisper FT Spark (:2022) → Gemma 4 omni
# (:8089, SSE) → VoxCPM2 v8 Spark (:8884 → Nano-vLLM :8026, TTS par phrase).
# Reconstruction 2026-07-08 du POC 2026-06-18 (original gitignoré perdu avec
# l'effacement de ~/apple_all/voxcpm — désormais sous git dans scripts/).

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

VENV_PYTHON="$HOME/.venvs/fastrtc/bin/python"

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "ERROR: venv python introuvable à $VENV_PYTHON"
    exit 1
fi

# TTS : VoxCPM2 v8 sur DGX Spark via bridge OpenAI :8884 (sparklan primaire,
# mesh fallback). v8 = dernier fine-tune voix Michael (225 wav, 1000 steps).
export VOICE_TTS_URL="http://127.0.0.1:8884/v1/audio/speech"
export VOICE_TTS_MODEL="michael-v8"

exec "$VENV_PYTHON" /Users/michaelahern/ai-servers/scripts/voice_agent_webrtc.py
