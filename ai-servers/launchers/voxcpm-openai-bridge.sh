#!/bin/bash
# Pont OpenAI → VoxCPM (/v1/audio/speech → backend /tts ou pass-through)
# Port 8883 — surface utilisée par OpenClaw messages.tts

export PATH="/opt/homebrew/bin:/usr/bin:/bin"

# v6 mergé perdu ; v7 en ré-entraînement (2026-07-07) — fallback voix de base VoxCPM2 MLX
# (mlx-community/VoxCPM2-bf16 ; openbmb/VoxCPM2 = poids PyTorch, incompatibles loader mlx-audio).
# Ce bloc devient inactif dès que le ckpt v7 mergé existe.
V7_CKPT="/Users/michaelahern/apple_all/voxcpm/pipeline/voxcpm2-lora/checkpoints-merged-michael-v7-mlx-8bit"
if [ ! -d "$V7_CKPT" ]; then
  export VOXCPM_MODEL="${VOXCPM_MODEL:-mlx-community/VoxCPM2-bf16}"
fi

exec /opt/homebrew/bin/python3 /Users/michaelahern/ai-servers/scripts/voxcpm-openai-bridge.py \
  --host 127.0.0.1 \
  --port 8883 \
  --backend http://127.0.0.1:8025
