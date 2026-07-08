#!/bin/bash
# Agent vocal — frontend Gradio, port 7860
# micro → Whisper FT (:2022) → Gemma 4 omni (:8089, SSE) → VoxCPM2 v7 (:8025)
# Pipeline LLM→TTS par phrases : premier son ~1-2 s (realtime).
# Venv fastrtc (gradio 5.50) — réutilisé, pas de venv dédié.

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

VENV_PYTHON="$HOME/.venvs/fastrtc/bin/python"

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "ERROR: venv python introuvable à $VENV_PYTHON"
    exit 1
fi

exec "$VENV_PYTHON" /Users/michaelahern/ai-servers/scripts/voice_agent_gradio.py
