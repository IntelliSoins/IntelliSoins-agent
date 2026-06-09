#!/bin/bash
# Gemma 4 E4B Multimodal — Port 8088
# True multimodal: texte + image + video + audio natif (4B params, 8-bit)
# Via vMLX 1.3.27 (mlx-vlm 0.4.4, Gemma4 support)
# Apache 2.0 — Google DeepMind, April 2, 2026

export PATH="/Users/michaelahern/.local/bin:/opt/homebrew/bin:/usr/bin:/bin"
export HF_HOME="$HOME/.cache/huggingface"

exec vmlx serve mlx-community/gemma-4-e4b-it-8bit \
    --port 8088 \
    --host 127.0.0.1 \
    --is-mllm \
    --enable-auto-tool-choice \
    --tool-call-parser gemma4 \
    --reasoning-parser gemma4 \
    --served-model-name gemma-4-e4b
