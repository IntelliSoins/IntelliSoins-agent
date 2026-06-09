#!/bin/bash
# Signal Messenger REST API — Port 8094
# Local-only Docker wrapper around signal-cli-rest-api.

set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

ENV_FILE="$HOME/ai-servers/signal-agent-router/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

HOST="${SIGNAL_API_HOST:-127.0.0.1}"
PORT="${SIGNAL_API_PORT:-8094}"
MODE="${SIGNAL_API_MODE:-native}"
IMAGE="${SIGNAL_API_IMAGE:-bbernhard/signal-cli-rest-api:0.99}"
CONTAINER_NAME="${SIGNAL_API_CONTAINER_NAME:-ai-servers-signal-api}"
CONFIG_DIR="${SIGNAL_API_CONFIG_DIR:-$HOME/.local/share/signal-api}"
LOG_LEVEL="${SIGNAL_API_LOG_LEVEL:-info}"

mkdir -p "$CONFIG_DIR"

if ! command -v docker >/dev/null 2>&1; then
    echo "ERREUR: docker introuvable; requis pour signal-cli-rest-api" >&2
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "ERREUR: Docker ne repond pas; demarre Docker Desktop puis relance signal-api" >&2
    exit 1
fi

# launchd garde le process en vie; on remplace seulement le container gere par ce launcher.
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

exec docker run --rm \
    --name "$CONTAINER_NAME" \
    -p "${HOST}:${PORT}:8080" \
    -v "${CONFIG_DIR}:/home/.local/share/signal-cli" \
    -e "MODE=${MODE}" \
    -e "LOG_LEVEL=${LOG_LEVEL}" \
    -e "JSON_RPC_IGNORE_ATTACHMENTS=${JSON_RPC_IGNORE_ATTACHMENTS:-true}" \
    -e "JSON_RPC_IGNORE_STORIES=${JSON_RPC_IGNORE_STORIES:-true}" \
    "$IMAGE"
