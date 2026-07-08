#!/bin/bash
# Whisper large-v3-turbo STT — Port 2022
# Speech-to-text via MLX-Whisper FastAPI server

export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin"
# Sourcing HF token dynamically to avoid committing hard-coded secrets
if [ -z "$HF_TOKEN" ]; then
    if [ -f "$HOME/.cache/huggingface/token" ]; then
        HF_TOKEN=$(cat "$HOME/.cache/huggingface/token" 2>/dev/null)
    elif [ -f "$HOME/ai-servers/litellm-proxy/.env" ]; then
        HF_TOKEN=$(grep -E "^HF_TOKEN=" "$HOME/ai-servers/litellm-proxy/.env" | cut -d= -f2- | tr -d '"'\' 2>/dev/null)
    fi
fi
if [ -n "$HF_TOKEN" ]; then
    export HF_TOKEN
fi

# 2026-07-08 : PRO-G40 corrompu (2e fois) — retour sur le disque INTERNE.
# ~/services/whisper-finetune = workspace local (serveur + fine-tuning, venv-ft py3.14).
# Modèle: LoRA v2 voix Michael rescué du PRO-G40 (models/whisper-michael-mlx) ;
# rollback base : WHISPER_MODEL_PATH=mlx-community/whisper-large-v3-turbo.
# Dataset retrain v3 prêt : datasets/dictee-v3 (cf. tools/export_dictations_dataset.py).
WHISPER_DIR="$HOME/services/whisper-finetune"
VENV_PYTHON="$WHISPER_DIR/venv-ft/bin/python3"

if [[ ! -f "$VENV_PYTHON" ]]; then
    echo "ERROR: venv python not found at $VENV_PYTHON"
    exit 1
fi

cd "$WHISPER_DIR"
exec "$VENV_PYTHON" mlx_whisper_server.py
