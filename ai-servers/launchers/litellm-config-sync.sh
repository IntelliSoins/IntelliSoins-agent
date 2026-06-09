#!/bin/bash
# LiteLLM config/Admin UI sync watcher

export PATH="/Users/michaelahern/.venvs/litellm/bin:/opt/homebrew/opt/postgresql@17/bin:/opt/homebrew/bin:/usr/bin:/bin"
export DATABASE_URL="postgresql://michaelahern@localhost:5432/litellm"
export LITELLM_BASE_URL="http://127.0.0.1:8092"

if [ -f "$HOME/ai-servers/litellm-proxy/.env" ]; then
    set -a
    source "$HOME/ai-servers/litellm-proxy/.env"
    set +a
fi

LITELLM_MASTER_KEY=$(security find-generic-password -a "$USER" -s litellm-master-key -w 2>/dev/null)
LITELLM_SALT_KEY=$(security find-generic-password -a "$USER" -s litellm-salt-key -w 2>/dev/null)

if [ -z "$LITELLM_MASTER_KEY" ] || [ -z "$LITELLM_SALT_KEY" ]; then
    echo "ERREUR: Secrets manquants dans Keychain (litellm-master-key, litellm-salt-key)" >&2
    exit 1
fi

export LITELLM_MASTER_KEY
export LITELLM_SALT_KEY

exec "$HOME/.venvs/litellm/bin/python3" \
    "$HOME/ai-servers/scripts/litellm_config_sync.py" watch-all --interval 10
