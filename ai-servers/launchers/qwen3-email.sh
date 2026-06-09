#!/bin/bash
# Qwen3-8B Email LoRA — Port 8081
# Qwen3-8B (4-bit) + LoRA adapter email-style-v2

export HF_HOME="$HOME/.cache/huggingface"
export PATH="/Users/michaelahern/.venvs/mlx-openai-server/bin:/opt/homebrew/bin:/usr/bin:/bin"

exec mlx-openai-server launch \
    --model-path mlx-community/Qwen3-8B-4bit \
    --lora-paths /Users/michaelahern/ocr-finance/Finances_Assurances/adapters-email-style-v2 \
    --model-type lm \
    --port 8081 \
    --host 127.0.0.1 \
    --context-length 32768 \
    --decode-concurrency 1 \
    --log-level INFO \
    --no-log-file \
    --trust-remote-code
