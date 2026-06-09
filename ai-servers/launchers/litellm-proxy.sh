#!/bin/bash
# LiteLLM Proxy — Port 8092
# Router unifie: cloud (OpenAI) + 11 MLX chat/VLM + embeddings/rerank/audio
# Secrets via macOS Keychain, DB Postgres17 local, cache Redis db:1

export PATH="/Users/michaelahern/.venvs/litellm/bin:/opt/homebrew/bin:/usr/bin:/bin"

# Source les API keys cloud depuis le fichier .env
if [ -f "$HOME/ai-servers/litellm-proxy/.env" ]; then
    set -a
    source "$HOME/ai-servers/litellm-proxy/.env"
    set +a
fi

if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "REPLACE_ME" ]; then
    echo "ERREUR: OPENAI_API_KEY manquante dans ~/ai-servers/litellm-proxy/.env" >&2
    exit 1
fi

# Recupere secrets LiteLLM depuis le trousseau macOS
LITELLM_MASTER_KEY=$(security find-generic-password -a "$USER" -s litellm-master-key -w 2>/dev/null)
LITELLM_SALT_KEY=$(security find-generic-password -a "$USER" -s litellm-salt-key -w 2>/dev/null)

if [ -z "$LITELLM_MASTER_KEY" ] || [ -z "$LITELLM_SALT_KEY" ]; then
    echo "ERREUR: Secrets manquants dans Keychain (litellm-master-key, litellm-salt-key)" >&2
    exit 1
fi

export LITELLM_MASTER_KEY
export LITELLM_SALT_KEY
export DATABASE_URL="postgresql://michaelahern@localhost:5432/litellm"
export STORE_MODEL_IN_DB=True

# oMLX local gateway auth. Keep the key out of config.yaml.
if [ -z "$OMLX_API_KEY" ] && [ -f "$HOME/.omlx/settings.json" ]; then
    OMLX_API_KEY=$(/usr/bin/python3 -c 'import json, os; p=os.path.expanduser("~/.omlx/settings.json"); print((json.load(open(p)).get("auth") or {}).get("api_key") or "")' 2>/dev/null)
fi
if [ -n "$OMLX_API_KEY" ]; then
    export OMLX_API_KEY
fi

# Together AI (cloud US) — modeles chinois open-weight
TOGETHERAI_API_KEY=$(security find-generic-password -a "$USER" -s together-api-key -w 2>/dev/null)
if [ -z "$TOGETHERAI_API_KEY" ]; then
    echo "ERREUR: together-api-key manquant dans Keychain" >&2
    exit 1
fi
export TOGETHERAI_API_KEY

# Garde: regenerer le client Prisma si manquant (robustesse si venv recree)
LITELLM_PROXY_DIR="$HOME/.venvs/litellm/lib/python3.12/site-packages/litellm/proxy"
if ! "$HOME/.venvs/litellm/bin/python3" -c "import prisma" 2>/dev/null; then
    echo "[litellm-proxy] Prisma manquant, installation..." >&2
    "$HOME/.venvs/litellm/bin/pip" install prisma >&2 \
        || echo "[litellm-proxy] WARN: pip install prisma echoue" >&2
fi
if [ -f "$LITELLM_PROXY_DIR/schema.prisma" ] && \
   ! "$HOME/.venvs/litellm/bin/python3" -c "from prisma import Prisma" 2>/dev/null; then
    echo "[litellm-proxy] Generation client Prisma..." >&2
    (cd "$LITELLM_PROXY_DIR" && \
        "$HOME/.venvs/litellm/bin/prisma" generate >&2) \
        || echo "[litellm-proxy] WARN: prisma generate echoue" >&2
fi

exec litellm \
    --config "$HOME/ai-servers/litellm-proxy/config.yaml" \
    --port 8092 \
    --host 127.0.0.1
