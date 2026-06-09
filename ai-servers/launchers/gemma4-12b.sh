#!/bin/bash
# Gemma 4 12B Instruct — Port 8098
# Multimodal unifié (texte + vision), 12B params, 4-bit MLX (~11 GB)
# Via vMLX (pattern gemma4-e4b) — bascule agent vocal realtime (latence vs qwen35-35b thinking)

export PATH="/Users/michaelahern/.local/bin:/opt/homebrew/bin:/usr/bin:/bin"
export HF_HOME="$HOME/.cache/huggingface"

# Optimisations latence (Mac 128 GB RAM, usage vocal single-user) :
#   --kv-cache-quantization none : supprime le coût quantize/dequantize KV par token
#   --enable-prefix-cache : réutilise le KV du system prompt + historique entre tours
#   --enable-pld : prompt lookup decoding (drafts gratuits depuis le prompt)
exec vmlx serve mlx-community/gemma-4-12B-it-4bit \
    --port 8098 \
    --host 127.0.0.1 \
    --is-mllm \
    --enable-auto-tool-choice \
    --tool-call-parser gemma4 \
    --reasoning-parser gemma4 \
    --served-model-name gemma4-12b \
    --default-enable-thinking true \
    --default-repetition-penalty 1.15 \
    --kv-cache-quantization none \
    --enable-prefix-cache \
    --prefix-cache-size 50 \
    --enable-pld \
    --max-tokens 4096
