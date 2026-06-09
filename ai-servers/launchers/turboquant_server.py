#!/usr/bin/env python3
"""Wrapper to launch mlx-openai-server with TurboQuant KV-cache compression.

Patches make_prompt_cache and SDPA before the server CLI runs.
"""
import sys
import os

# Ensure site-packages app module is found, not a local app/ directory
cwd = os.getcwd()
sys.path = [p for p in sys.path if p != "" and p != "." and p != cwd]

# Apply TurboQuant patch
sys.path.insert(0, os.path.expanduser("~/ai-servers"))
import turboquant_patch
turboquant_patch.apply()

# Launch the server CLI
if __name__ == '__main__':
    from app.cli import cli
    cli()
