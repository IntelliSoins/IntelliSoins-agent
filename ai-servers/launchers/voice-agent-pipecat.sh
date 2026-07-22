#!/bin/bash
# Pipecat WebRTC P0/P1 — parallel canary on :8027; legacy FastRTC stays on :8024.

set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

VENV_PYTHON="$HOME/.venvs/pipecat-voice/bin/python"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$SCRIPT_DIR/scripts/voice_agent_pipecat.py"
MIGRATE="$SCRIPT_DIR/scripts/voice_agent_migrate.py"

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "ERROR: venv python introuvable à $VENV_PYTHON"
    echo "Installer: uv venv ~/.venvs/pipecat-voice --python 3.12"
    echo "Puis: uv pip install --python ~/.venvs/pipecat-voice/bin/python -r $SCRIPT_DIR/requirements-voice-agent-pipecat.txt"
    exit 1
fi

# Clé API vLLM Spark — jamais en dur.
ENV_FILE="$SCRIPT_DIR/litellm-proxy/.env"
if [[ -f "$ENV_FILE" ]]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

# Sparklan primaire, mesh WireGuard secondaire. Aucun fallback vers un modèle Mac.
pick_spark_host() {
    if curl -sf --connect-timeout 2 --max-time 3 "http://10.0.1.1:2022/health" >/dev/null 2>&1; then
        echo "10.0.1.1"
        return
    fi
    if curl -sf --connect-timeout 3 --max-time 5 "http://10.0.0.5:2022/health" >/dev/null 2>&1; then
        echo "10.0.0.5"
        return
    fi
    echo "10.0.0.5"
}

SPARK_HOST="${VOICE_SPARK_HOST:-$(pick_spark_host)}"
echo "[voice-agent-pipecat] Spark host: $SPARK_HOST"

export VOICE_WHISPER_URL="http://${SPARK_HOST}:2022/v1/audio/transcriptions"
export VOICE_LLM_URL="http://${SPARK_HOST}:8000/v1/chat/completions"
export VOICE_LLM_MODEL="qwen3.5-4b-finetunev2"
export VOICE_LLM_KEY="${SPARK_VLLM_API_KEY:-}"
export VOICE_TTS_URL="http://127.0.0.1:8884/v1/audio/speech"
export VOICE_TTS_MODEL="michael-v8"

# Trusted local identity for this WebRTC canary. Telephony adapters must replace
# this with a contact id resolved server-side; the LLM cannot override it.
export VOICE_SUBJECT_ID="${VOICE_SUBJECT_ID:-michael-local}"
export VOICE_EXPLICIT_CONSENT_VERIFIED="${VOICE_EXPLICIT_CONSENT_VERIFIED:-0}"

# Existing speaker-echo evidence makes non-interruptible the safe default.
# Enable only after an AEC/headset canary validates barge-in.
export VOICE_BARGE_IN="${VOICE_BARGE_IN:-0}"
export PIPECAT_SCTP_MAX_CHUNK_SIZE="${PIPECAT_SCTP_MAX_CHUNK_SIZE:-1100}"

# PostgreSQL exact log + confirmed memory are required in the production launcher.
export VOICE_DB_DSN="${VOICE_DB_DSN:-postgresql:///voice_agent}"
export VOICE_DB_ENABLED=1
"$VENV_PYTHON" "$MIGRATE"

# HTTPS is mandatory for browser microphone access on the WireGuard address.
TLS_DIR="${VOICE_TLS_DIR:-$HOME/.cache/voice-agent/tls}"
CERT="$TLS_DIR/voice-agent.crt"
KEY="$TLS_DIR/voice-agent.key"
mkdir -p "$TLS_DIR"

if [[ ! -f "$CERT" || ! -f "$KEY" ]]; then
    openssl req -x509 -newkey rsa:2048 -nodes \
        -keyout "$KEY" -out "$CERT" -days 365 \
        -subj "/CN=voice-agent-pipecat" \
        -addext "subjectAltName=IP:10.0.0.2,IP:127.0.0.1,DNS:localhost" \
        -addext "extendedKeyUsage=serverAuth" 2>/dev/null \
        || openssl req -x509 -newkey rsa:2048 -nodes \
            -keyout "$KEY" -out "$CERT" -days 365 \
            -subj "/CN=voice-agent-pipecat"
fi

export VOICE_SSL_CERT="$CERT"
export VOICE_SSL_KEY="$KEY"
export VOICE_PIPECAT_HOST="${VOICE_PIPECAT_HOST:-10.0.0.2}"
export VOICE_PIPECAT_PORT="${VOICE_PIPECAT_PORT:-8027}"

exec "$VENV_PYTHON" "$SCRIPT"
