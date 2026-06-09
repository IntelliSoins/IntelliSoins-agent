#!/bin/bash
# NLLB-200 Traduction — Port 6060
# Neural machine translation via NLLB-200

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

cd /Users/michaelahern/master-IA/tools/live-translator

exec /Users/michaelahern/master-IA/tools/live-translator/venv/bin/python \
    translation_server.py
