#!/bin/bash
# litellm-pgvector sidecar — Port 8093
# OpenAI-compatible Vector Stores API backed by Postgres17 + pgvector (1024D)
# Embeddings via LiteLLM proxy (8092) → qwen3-embedding MLX (8084)
# 100% local — Loi 25 compliant

set -euo pipefail

export PATH="/Users/michaelahern/ai-servers/litellm-pgvector/.venv/bin:/opt/homebrew/bin:/usr/bin:/bin"

cd /Users/michaelahern/ai-servers/litellm-pgvector

# Charger .env (DATABASE_URL, SERVER_API_KEY, EMBEDDING__*, HOST, PORT)
if [ -f "$HOME/ai-servers/litellm-pgvector/.env" ]; then
    set -a
    source "$HOME/ai-servers/litellm-pgvector/.env"
    set +a
else
    echo "ERREUR: .env manquant dans ~/ai-servers/litellm-pgvector/" >&2
    exit 1
fi

# Garde: regenerer client Prisma si manquant (robustesse si venv recree)
if ! "/Users/michaelahern/ai-servers/litellm-pgvector/.venv/bin/python3" \
        -c "from prisma import Prisma" 2>/dev/null; then
    echo "[litellm-pgvector] Generation client Prisma..." >&2
    (cd "$HOME/ai-servers/litellm-pgvector" && \
        prisma generate >&2) \
        || echo "[litellm-pgvector] WARN: prisma generate echoue" >&2
fi

exec /Users/michaelahern/ai-servers/litellm-pgvector/.venv/bin/python -m uvicorn \
    main:app \
    --host "$HOST" \
    --port "$PORT"
