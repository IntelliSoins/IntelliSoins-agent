#!/bin/bash
# VoxCPM2 LoRA Michael v7 (MLX 8bit) — Port 8025
# OpenAI-compatible /v1/audio/speech via mlx-audio, ou voxcpm_server_mlx.py si présent.

export PATH="/Users/michaelahern/.local/bin:/opt/homebrew/bin:/usr/bin:/bin"
export PYTHONPATH="$HOME/apple_all/mlx-audio${PYTHONPATH:+:$PYTHONPATH}"

VOXCPM_DIR="$HOME/apple_all/voxcpm/pipeline/voxcpm2-lora"
VOXCPM_MLX_CKPT="${VOXCPM_MLX_CKPT:-$VOXCPM_DIR/checkpoints-merged-michael-v7-mlx-8bit}"
VENV="$HOME/.venvs/mlx-audio/bin/python"
LOG_DIR="$HOME/ai-servers/logs/voxcpm-tts-server"

if [ -f "$VOXCPM_DIR/voxcpm_server_mlx.py" ]; then
  export VOXCPM_MLX_CKPT
  export VOXCPM_TIMESTEPS="${VOXCPM_TIMESTEPS:-6}"
  export VOXCPM_CFG="${VOXCPM_CFG:-2.0}"
  cd "$VOXCPM_DIR" || exit 1
  exec "$VENV" "$VOXCPM_DIR/voxcpm_server_mlx.py"
fi

# Fallback: v6 mergé perdu (~/apple_all/voxcpm effacé, rapport 2026-07-05) ; v7 en ré-entraînement
# (relancé 2026-07-07, merge MLX 8bit à produire à la fin — voir rule apple_all voxcpm.md).
# mlx_audio.server charge les modèles à la demande ; la voix de base VoxCPM2 reste servie
# tant que le checkpoint fine-tuné v7 n'est pas mergé.
if [ ! -d "$VOXCPM_MLX_CKPT" ]; then
  echo "WARN: checkpoint VoxCPM v7 introuvable: $VOXCPM_MLX_CKPT — fallback voix de base VoxCPM2" >&2
fi

cd "$HOME/ai-servers" || exit 1
mkdir -p "$LOG_DIR"
exec "$VENV" -m mlx_audio.server \
  --host 127.0.0.1 \
  --port 8025 \
  --log-dir "$LOG_DIR"
