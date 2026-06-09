#!/bin/bash
# OpenClaw (IntelliSoins Gateway) — Port 18789
# Interface agentique locale pour IntelliSoins avec interface en français

export PATH="/opt/homebrew/bin:/usr/bin:/bin"

# Exécute la gateway OpenClaw en premier plan pour launchd
exec openclaw gateway run --port 18789 --bind loopback
