#!/bin/bash
# Spark VoxCPM OpenAI bridge — Port 8884
# Traduit /v1/audio/speech (OpenAI) → /generate (Nano-vLLM Spark).
# Backend : sparklan http://10.0.1.1:8026 (~4 ms maison) primaire, mesh
# http://10.0.0.5:8026 (~82 ms hub VPS) fallback — géré dans spark-voxcpm-bridge.py.
# Consommateurs : Hammerspoon ⌥v (init.lua), agent vocal (voice-agent-webrtc.sh),
# LiteLLM :8092 (spark-voxcpm-v8).

export PATH="/Users/michaelahern/.local/bin:/opt/homebrew/bin:/usr/bin:/bin"
VENV="$HOME/.venvs/mlx-audio/bin/python"

cd "$HOME/ai-servers" || exit 1
exec "$VENV" scripts/spark-voxcpm-bridge.py \
  --host 127.0.0.1 \
  --port 8884
