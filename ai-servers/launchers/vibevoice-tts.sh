#!/bin/bash
# VibeVoice Realtime 0.5B TTS — Port 8882
# Text-to-speech via mlx-audio server (OpenAI-compatible)

export PATH="/Users/michaelahern/.local/bin:/opt/homebrew/bin:/usr/bin:/bin"

cd "/Users/michaelahern/ai-servers" || exit 1

exec mlx_audio.server --host 127.0.0.1 --port 8882 --log-dir "/Users/michaelahern/ai-servers/logs/vibevoice-tts-server" --realtime-model /Users/michaelahern/nlp/whisper-finetune/datasets/vibevoice-fused
