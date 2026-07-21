#!/usr/bin/env bash
# PATCH ai-spark 2026-07-12 — garde-fou mémoire avant fine-tuning (task-102).
# Incident : FT Qwen3.5-4B lancé avec 5 containers serving résidents GPU
# → starvation mémoire unifiée GB10 (121 Go) → toute inférence GPU gelée
# + sshd wedged. Ce preflight refuse de démarrer un FT sans marge suffisante.
#
# Usage : ./finetune-preflight.sh [--min-free-gb N] [--auto-stop]
#   --min-free-gb N : marge MemAvailable minimale requise (défaut 60)
#   --auto-stop     : arrête whisper/embeddings/reranker/docling/translation
#                     (garde voxcpm-tts) si la marge est insuffisante
# Intégration sparkctl (à faire manuellement, cf. apply-spark-fixes.sh) :
#   la commande `finetune start` doit appeler ce script et s'arrêter si exit != 0.
set -euo pipefail

MIN_FREE_GB=60
AUTO_STOP=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --min-free-gb) MIN_FREE_GB="$2"; shift 2 ;;
    --auto-stop)   AUTO_STOP=true; shift ;;
    *) echo "arg inconnu: $1" >&2; exit 2 ;;
  esac
done

# Containers serving GPU arrêtables pendant un FT (voxcpm exclu : voix Michael).
STOPPABLE_REGEX='whisper|embeddings|reranker|docling|translation'

free_gb() {
  awk '/MemAvailable/ {printf "%d", $2/1024/1024}' /proc/meminfo
}

swap_used_gb() {
  awk '/SwapTotal/ {t=$2} /SwapFree/ {f=$2} END {printf "%d", (t-f)/1024/1024}' /proc/meminfo
}

echo "=== finetune-preflight ($(date '+%F %T')) ==="
AVAIL=$(free_gb)
SWAP=$(swap_used_gb)
echo "MemAvailable : ${AVAIL} Go (minimum requis : ${MIN_FREE_GB} Go)"
echo "Swap utilisé : ${SWAP} Go"

echo "--- Containers GPU-résidents actifs ---"
docker ps --format '{{.Names}}\t{{.Status}}' | grep -Ei "${STOPPABLE_REGEX}|voxcpm|qwen|vllm" || echo "(aucun)"

if [[ "$SWAP" -gt 4 ]]; then
  echo "⚠️  Swap déjà sous pression (${SWAP} Go) — le host est probablement déjà chargé."
fi

if [[ "$AVAIL" -ge "$MIN_FREE_GB" ]]; then
  echo "✅ Marge suffisante (${AVAIL} ≥ ${MIN_FREE_GB} Go) — FT autorisé."
  exit 0
fi

echo "❌ Marge INSUFFISANTE (${AVAIL} < ${MIN_FREE_GB} Go)."
if [[ "$AUTO_STOP" == "true" ]]; then
  echo "--auto-stop : arrêt des containers serving (voxcpm conservé)..."
  docker ps --format '{{.Names}}' | grep -Ei "$STOPPABLE_REGEX" | while read -r c; do
    echo "  docker stop $c"
    docker stop "$c" >/dev/null
  done
  sleep 5
  AVAIL=$(free_gb)
  echo "MemAvailable après arrêt : ${AVAIL} Go"
  if [[ "$AVAIL" -ge "$MIN_FREE_GB" ]]; then
    echo "✅ Marge récupérée — FT autorisé. (Relancer les services après : sparkctl up core)"
    exit 0
  fi
  echo "❌ Toujours insuffisant même après arrêt du serving. FT refusé."
  exit 1
fi
echo "Relancer avec --auto-stop pour libérer le serving (voxcpm conservé),"
echo "ou arrêter manuellement : docker ps | grep -E '${STOPPABLE_REGEX}'"
exit 1
