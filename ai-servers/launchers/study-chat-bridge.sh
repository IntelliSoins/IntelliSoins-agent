#!/bin/bash
# Pont d'étude concept-interactif — Port 8765
# Relaie les fiches HTML → LiteLLM (Qwen3.6 local) ou Cursor SDK.
# Config : apple_all/.claude/skills/concept-interactif/server/study-chat-bridge.env

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

BRIDGE_DIR="$HOME/apple_all/.claude/skills/concept-interactif/server"
ENVFILE="$BRIDGE_DIR/study-chat-bridge.env"
PYTHON="/opt/homebrew/bin/python3"

if [ -f "$ENVFILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENVFILE"
    set +a
fi

if [ "${STUDY_CHAT_BACKEND:-cursor}" = "litellm" ]; then
    if [ -f "$HOME/ai-servers/litellm-proxy/.env" ]; then
        set -a
        # shellcheck disable=SC1091
        source "$HOME/ai-servers/litellm-proxy/.env"
        set +a
    fi
    if [ -z "${LITELLM_MASTER_KEY:-}" ]; then
        LITELLM_MASTER_KEY=$(security find-generic-password -a "$USER" -s litellm-master-key -w 2>/dev/null || true)
        export LITELLM_MASTER_KEY
    fi
    if [ -z "${LITELLM_MASTER_KEY:-}" ] && [ -z "${STUDY_CHAT_LITELLM_KEY:-}" ]; then
        echo "ERREUR: clé LiteLLM introuvable (Keychain litellm-master-key)" >&2
        exit 1
    fi
fi

cd "$BRIDGE_DIR"
exec "$PYTHON" "$BRIDGE_DIR/study_chat_bridge.py"
