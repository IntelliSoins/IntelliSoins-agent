#!/bin/bash
# Kokoro TTS — Port 8880
# Text-to-speech via mlx-audio server (OpenAI-compatible)

export PATH="/Users/michaelahern/.local/bin:/opt/homebrew/bin:/usr/bin:/bin"

# mlx-audio 0.4.3 creates a server-log dir relative to CWD; launchd's CWD is "/" (read-only).
# Run from a writable dir and point --log-dir at the project's logs folder.
cd "/Users/michaelahern/ai-servers" || exit 1

exec mlx_audio.server --host 127.0.0.1 --port 8880 --log-dir "/Users/michaelahern/ai-servers/logs/mlx-audio-server"
