#!/bin/bash
# BGE-reranker-v2-m3 — Port 8085
# Reranker server for RAG pipeline
# Uses internal disk cache

export HF_HOME="$HOME/.cache/huggingface"
export HUGGINGFACE_HUB_CACHE="$HOME/.cache/huggingface/hub"

cd /Users/michaelahern/intellisoins-scripts
exec /opt/homebrew/bin/python3 mlx-reranker-server.py --port 8085
