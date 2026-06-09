#!/bin/bash
# Qwen3-8B Merged + Tools — Port 8083
# Qwen3-8B (4-bit) + LoRA merged adapter + Hermes tool calling

export HF_HOME="$HOME/.cache/huggingface"
export PATH="/Users/michaelahern/.venvs/mlx-openai-server/bin:/opt/homebrew/bin:/usr/bin:/bin"

exec mlx-openai-server launch \
    --model-path mlx-community/Qwen3-8B-4bit \
    --lora-paths /Users/michaelahern/ocr-finance/Finances_Assurances/adapters-qwen3-merged \
    --model-type lm \
    --port 8083 \
    --host 127.0.0.1 \
    --context-length 32768 \
    --decode-concurrency 1 \
    --enable-auto-tool-choice \
    --tool-call-parser hermes \
    --log-level INFO \
    --no-log-file \
    --trust-remote-code
