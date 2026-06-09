#!/bin/bash
# Nemotron 30B Tools — Port 8082
# NVIDIA Nemotron-3-Nano-30B with tool calling (4-bit)
# Note: ~15GB model, will auto-download on first launch if not cached

export HF_HOME="$HOME/.cache/huggingface"
export PATH="/Users/michaelahern/.venvs/mlx-openai-server/bin:/opt/homebrew/bin:/usr/bin:/bin"

exec mlx-openai-server launch \
    --model-path mlx-community/NVIDIA-Nemotron-3-Nano-30B-A3B-4bit \
    --model-type lm \
    --port 8082 \
    --host 127.0.0.1 \
    --context-length 262144 \
    --decode-concurrency 1 \
    --enable-auto-tool-choice \
    --tool-call-parser nemotron3_nano \
    --reasoning-parser nemotron3_nano \
    --log-level INFO \
    --no-log-file \
    --trust-remote-code
