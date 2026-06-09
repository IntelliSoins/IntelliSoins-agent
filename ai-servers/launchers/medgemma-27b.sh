#!/bin/bash
# MedGemma 27B Text — Port 8080
# LLM medical 27B (4-bit) via mlx-openai-server
# TurboQuant V2 3-bit KV-cache compression (3.8x vs fp16)
# No external disk required (model in local HF cache)
# To disable TurboQuant: export TURBOQUANT_DISABLED=1

export PATH="/Users/michaelahern/.venvs/mlx-openai-server/bin:/opt/homebrew/bin:/usr/bin:/bin"
export HF_HOME="$HOME/.cache/huggingface"
export TURBOQUANT_BITS=3

exec python /Users/michaelahern/ai-servers/launchers/turboquant_server.py launch \
    --model-path mlx-community/medgemma-27b-text-it-4bit \
    --model-type lm \
    --port 8080 \
    --host 127.0.0.1 \
    --decode-concurrency 1 \
    --log-level INFO \
    --no-log-file \
    --enable-auto-tool-choice \
    --tool-call-parser functiongemma
