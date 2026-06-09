#!/bin/bash
# Docling OCR/Extraction — Port 5010
# Document extraction and OCR via docling-serve

export PATH="/Users/michaelahern/.venvs/docling-mlx/bin:/opt/homebrew/bin:/usr/bin:/bin"

exec docling-serve run \
    --host 127.0.0.1 \
    --port 5010 \
    --no-reload
