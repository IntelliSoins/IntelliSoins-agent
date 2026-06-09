#!/bin/bash
# GLiNER NER HTTP Server — Port 8091
# Biomedical entity extraction for IntelliSoins (model: Ihor/gliner-biomed-large-v1.0)
# Uses dedicated venv ~/venvs/gliner/ with gliner + fastapi pre-installed

export HF_HOME="$HOME/.cache/huggingface"
export HUGGINGFACE_HUB_CACHE="$HOME/.cache/huggingface/hub"

exec /Users/michaelahern/venvs/gliner/bin/python \
    /Users/michaelahern/intellisoins-pubmed/scripts/gliner-http-server.py \
    --host 127.0.0.1 \
    --port 8091
