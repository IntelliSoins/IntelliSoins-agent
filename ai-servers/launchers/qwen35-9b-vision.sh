#!/bin/bash
# Qwen3.5-9B MLX Vision — Port 8089
# VLM 9B (4-bit, 5.6 Go) + tool calling + reasoning pour agentic multi-tour
# Via vllm-mlx 0.2.9+ (hybrid model batching, content-based vision cache 28x, native video M-RoPE)
# Testé 2026-04-24: texte 0.6s, vision 2.6s/150 tok

export PATH="/Users/michaelahern/.venvs/vllm-mlx/bin:/opt/homebrew/bin:/usr/bin:/bin"
export HF_HOME="$HOME/.cache/huggingface"

exec vllm-mlx serve mlx-community/Qwen3.5-9B-MLX-4bit \
    --port 8089 --host 127.0.0.1 \
    --served-model-name qwen3.5-9b-vision \
    --enable-auto-tool-choice \
    --tool-call-parser qwen3_coder \
    --reasoning-parser qwen3 \
    --max-request-tokens 262144 \
    --max-tokens 131072 \
    --max-cache-blocks 4096 \
    --paged-cache-block-size 64 \
    --use-paged-cache \
    --kv-cache-quantization \
    --kv-cache-quantization-bits 8 \
    --kv-cache-min-quantize-tokens 1024 \
    --enable-prefix-cache \
    --continuous-batching \
    --max-num-seqs 4 \
    --ssd-cache-dir "$HOME/.cache/vllm-mlx-ssd" \
    --ssd-cache-max-gb 50 \
    --cache-memory-percent 0.35
