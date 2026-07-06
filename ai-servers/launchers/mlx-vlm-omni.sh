#!/bin/bash
# mlx-vlm-omni — Port 8089
# Serveur omni gemma-4-12B (mlx-vlm) : texte + image + audio + vidéo (4 modalités)
# autostart:false — démarrage manuel sous contrôle RAM (cycle stop/start géré par la task de vérif).

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export HF_HOME="$HOME/.cache/huggingface"

# Token HF dynamique (pas de secret en dur)
if [ -z "$HF_TOKEN" ] && [ -f "$HOME/.cache/huggingface/token" ]; then
    HF_TOKEN=$(cat "$HOME/.cache/huggingface/token" 2>/dev/null)
fi
[ -n "$HF_TOKEN" ] && export HF_TOKEN

VENV_PYTHON="$HOME/.venvs/mlx-vlm/bin/python"

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "ERROR: venv python introuvable à $VENV_PYTHON"
    exit 1
fi

exec "$VENV_PYTHON" -m mlx_vlm.server \
    --host 127.0.0.1 \
    --port 8089 \
    --model mlx-community/gemma-4-12B-it-8bit
