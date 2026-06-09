#!/bin/bash
# Script de comparaison omlx vs vllm-mlx vs vmlx vs mlxcel sur Qwen3.5-9B-MLX-4bit

set -e
export PATH="/Users/michaelahern/.local/bin:/opt/homebrew/bin:/usr/bin:/usr/sbin:/bin"
export HF_HOME="$HOME/.cache/huggingface"

echo "======================================================"
echo " DÉBUT DU BENCHMARK COMPARATIF (MODÈLE UNIQUE QWEN 9B) "
echo "======================================================"

# 1. VLLM-MLX (port 8089) - Déjà en cours d'exécution
echo -e "\n>>> 1. Benchmarking VLLM-MLX..."
python3 benchmarks/cache-bench.py --url http://127.0.0.1:8089 --model qwen3.5-9b-vision --prompt-tokens 256 --gen-tokens 32

# 2. OMLX (port 8010) - Déjà en cours d'exécution
echo -e "\n>>> 2. Benchmarking oMLX..."
python3 benchmarks/cache-bench.py --url http://127.0.0.1:8010 --model Qwen3.5-9B-MLX-4bit --api-key omlx-pwjr4cw2lgojrqjy --prompt-tokens 256 --gen-tokens 32

# 3. VMLX (démarrage temporaire sur le port 8999)
echo -e "\n>>> 3. Benchmarking VMLX..."
vmlx serve mlx-community/Qwen3.5-9B-MLX-4bit --port 8999 --host 127.0.0.1 > logs/vmlx-temp.log 2>&1 &
VMLX_PID=$!

echo "Attente du démarrage de VMLX..."
for i in {1..30}; do
    if lsof -i :8999 -sTCP:LISTEN >/dev/null; then
        echo "VMLX est en ligne."
        break
    fi
    sleep 2
done

if ! lsof -i :8999 -sTCP:LISTEN >/dev/null; then
    echo "Erreur: VMLX n'a pas pu démarrer."
    cat logs/vmlx-temp.log
    kill $VMLX_PID 2>/dev/null || true
    exit 1
fi

python3 benchmarks/cache-bench.py --url http://127.0.0.1:8999 --model mlx-community/Qwen3.5-9B-MLX-4bit --prompt-tokens 256 --gen-tokens 32 || true

echo "Arrêt de VMLX..."
kill $VMLX_PID 2>/dev/null || true
wait $VMLX_PID 2>/dev/null || true

# 4. MLXCEL (démarrage temporaire sur le port 8998)
echo -e "\n>>> 4. Benchmarking MLXCEL..."
mlxcel-server -m mlx-community/Qwen3.5-9B-MLX-4bit --port 8998 --host 127.0.0.1 -c 8192 > logs/mlxcel-temp.log 2>&1 &
MLXCEL_PID=$!

echo "Attente du démarrage de MLXCEL..."
for i in {1..30}; do
    if lsof -i :8998 -sTCP:LISTEN >/dev/null; then
        echo "MLXCEL est en ligne."
        break
    fi
    sleep 2
done

if ! lsof -i :8998 -sTCP:LISTEN >/dev/null; then
    echo "Erreur: MLXCEL n'a pas pu démarrer."
    cat logs/mlxcel-temp.log
    kill $MLXCEL_PID 2>/dev/null || true
    exit 1
fi

python3 benchmarks/cache-bench.py --url http://127.0.0.1:8998 --model mlx-community/Qwen3.5-9B-MLX-4bit --prompt-tokens 256 --gen-tokens 32 || true

echo "Arrêt de MLXCEL..."
kill $MLXCEL_PID 2>/dev/null || true
wait $MLXCEL_PID 2>/dev/null || true

echo -e "\n======================================================"
echo " BENCHMARK COMPARATIF TERMINÉ "
echo "======================================================"
