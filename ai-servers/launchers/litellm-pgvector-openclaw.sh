#!/bin/bash
# litellm-pgvector-openclaw sidecar — Port 8100
# Instance dediee au projet OpenClaw/OpenIntellisoins (DB openclaw_pgvector)
# Meme code que litellm-pgvector (8093), seul l'env differe (.env.openclaw)
# Embeddings via LiteLLM proxy (8092) → qwen3-embedding MLX (8084)
# 100% local — Loi 25 compliant

set -euo pipefail

export PATH="/Users/michaelahern/ai-servers/litellm-pgvector/.venv/bin:/opt/homebrew/bin:/usr/bin:/bin"

cd /Users/michaelahern/ai-servers/litellm-pgvector

# Charger .env.openclaw (DATABASE_URL openclaw_pgvector, PORT 8100, SERVER_API_KEY, EMBEDDING__*)
if [ -f "$HOME/ai-servers/litellm-pgvector/.env.openclaw" ]; then
    set -a
    source "$HOME/ai-servers/litellm-pgvector/.env.openclaw"
    set +a
else
    echo "ERREUR: .env.openclaw manquant dans ~/ai-servers/litellm-pgvector/" >&2
    exit 1
fi

# Garde: regenerer client Prisma si manquant (robustesse si venv recree)
if ! "/Users/michaelahern/ai-servers/litellm-pgvector/.venv/bin/python3" \
        -c "from prisma import Prisma" 2>/dev/null; then
    echo "[litellm-pgvector-openclaw] Generation client Prisma..." >&2
    (cd "$HOME/ai-servers/litellm-pgvector" && \
        prisma generate >&2) \
        || echo "[litellm-pgvector-openclaw] WARN: prisma generate echoue" >&2
fi

exec /Users/michaelahern/ai-servers/litellm-pgvector/.venv/bin/python -m uvicorn \
    main:app \
    --host "$HOST" \
    --port "$PORT"
