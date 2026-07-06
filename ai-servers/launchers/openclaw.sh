#!/bin/bash
# OpenClaw (IntelliSoins Gateway) — Port 18789
# Interface agentique locale pour IntelliSoins avec interface en français

export PATH="/opt/homebrew/bin:/usr/bin:/bin"

OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-$(security find-generic-password -a "$USER" -s openrouter-api-key -w 2>/dev/null)}"
if [ -n "${OPENROUTER_API_KEY:-}" ]; then
    export OPENROUTER_API_KEY
fi

# Exécute la gateway OpenClaw en premier plan pour launchd
exec openclaw gateway run --port 18789 --bind loopback
