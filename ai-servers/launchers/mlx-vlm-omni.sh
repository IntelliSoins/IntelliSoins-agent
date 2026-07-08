#!/bin/bash
# mlx-vlm-omni — Port 8089
# Serveur omni gemma-4-12B (mlx-vlm) : texte + image + audio + vidéo (4 modalités)
# autostart:true depuis 2026-07-07 — backend de l'agent vocal Hammerspoon (⌥⌘ç / ⌥4).
#
# Optimisations vitesse (2026-07-07, agent vocal) :
#   - APC_ENABLED=1 : Automatic Prefix Caching (exact, par blocs de 16 tokens).
#     L'agent vocal renvoie system + ~30 schémas d'outils + historique à CHAQUE tour ;
#     sans APC chaque requête re-prefillait tout (TTFT ~9.3 s à 4k tokens, mesuré).
#     Pool défaut 2048 blocs = 32k tokens cachés, LRU.
#   - --draft-model gemma-4-12B-it-assistant-4bit (MTP, 258 Mo) : décodage spéculatif
#     natif Gemma 4 dans le batch generator (compatible APC + continuous batching).
#     Limite upstream : response_format structuré + thinking_budget refusés avec drafter.
#   - --prefill-step-size 4096 : accélère le prefill à froid (défaut 2048).

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

# Automatic Prefix Caching — coupe le TTFT des tours suivants de l'agent vocal
export APC_ENABLED=1

exec "$VENV_PYTHON" -m mlx_vlm.server \
    --host 127.0.0.1 \
    --port 8089 \
    --model mlx-community/gemma-4-12B-it-8bit \
    --draft-model mlx-community/gemma-4-12B-it-assistant-4bit \
    --draft-kind mtp \
    --prefill-step-size 4096
