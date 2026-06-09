#!/bin/bash
# Signal Agent Router — Port 8096
# Receives allowed Signal messages and routes read-only replies via LiteLLM.

set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

ROOT="$HOME/ai-servers"
ENV_FILE="$ROOT/signal-agent-router/.env"

if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

export SIGNAL_AGENT_ROOT="${SIGNAL_AGENT_ROOT:-$ROOT}"
export SIGNAL_ROUTER_HOST="${SIGNAL_ROUTER_HOST:-127.0.0.1}"
export SIGNAL_ROUTER_PORT="${SIGNAL_ROUTER_PORT:-8096}"
export SIGNAL_API_BASE="${SIGNAL_API_BASE:-http://127.0.0.1:8094}"
export LITELLM_API_BASE="${LITELLM_API_BASE:-http://127.0.0.1:8092/v1}"
export LITELLM_MODEL="${LITELLM_MODEL:-qwen35-9b-vision}"

exec /usr/bin/env python3 "$ROOT/scripts/signal_agent_router.py"
