#!/bin/bash
# mlxcel — Port 8097
# Moteur d'inférence Rust native direct C++ MLX
# Modèle par défaut : Llama 3.2 3B Instruct 4-bit

export PATH="/Users/michaelahern/.local/bin:/opt/homebrew/bin:/usr/bin:/bin"
export HF_HOME="$HOME/.cache/huggingface"

exec mlxcel-server \
    -m mlx-community/Llama-3.2-3B-Instruct-4bit \
    --port 8097 \
    --host 127.0.0.1 \
    -c 8192
