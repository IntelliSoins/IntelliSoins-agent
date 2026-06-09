#!/bin/bash
# Qwen3-Embedding-0.6B — Port 8084
# Embedding server (1024D) for pgvector RAG
# Uses internal disk cache

export HF_HOME="$HOME/.cache/huggingface"
export HUGGINGFACE_HUB_CACHE="$HOME/.cache/huggingface/hub"

exec /opt/homebrew/bin/python3 /Users/michaelahern/ai-servers/scripts/embedding-server.py \
    --port 8084 \
    --host 127.0.0.1 \
    --model Qwen/Qwen3-Embedding-0.6B
