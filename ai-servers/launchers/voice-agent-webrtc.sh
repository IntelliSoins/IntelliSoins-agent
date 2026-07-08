#!/bin/bash
# Agent vocal — front WebRTC FastRTC (UI Gradio), port 8024
# micro WebRTC + VAD Silero + barge-in → Whisper FT (:2022) → Gemma 4 omni
# (:8089, SSE) → VoxCPM2 v7 (:8025, TTS par phrase pendant la génération).
# Reconstruction 2026-07-08 du POC 2026-06-18 (original gitignoré perdu avec
# l'effacement de ~/apple_all/voxcpm — désormais sous git dans scripts/).

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

VENV_PYTHON="$HOME/.venvs/fastrtc/bin/python"

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "ERROR: venv python introuvable à $VENV_PYTHON"
    exit 1
fi

exec "$VENV_PYTHON" /Users/michaelahern/ai-servers/scripts/voice_agent_webrtc.py
