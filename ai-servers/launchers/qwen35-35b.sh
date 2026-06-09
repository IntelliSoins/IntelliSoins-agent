#!/bin/bash
# Qwen3.5 35B MoE — Port 8087
# Qwen3.5-35B-A3B (MoE, ~3.5B active params) with tool calling (4-bit)
# Primary agentic model for OpenClaw
# Migrated to vMLX engine for advanced agentic long-context caching

export PATH="/Users/michaelahern/.local/bin:/opt/homebrew/bin:/usr/bin:/bin"
export HF_HOME="$HOME/.cache/huggingface"

exec vmlx serve mlx-community/Qwen3.5-35B-A3B-4bit \
    --port 8087 \
    --host 127.0.0.1 \
    --enable-auto-tool-choice \
    --tool-call-parser auto \
    --reasoning-parser auto \
    --kv-cache-quantization q4 \
    --use-paged-cache \
    --enable-prefix-cache \
    --prefix-cache-size 100 \
    --enable-disk-cache \
    --enable-pld \
    --max-cache-blocks 4000 \
    --max-tokens 32768
