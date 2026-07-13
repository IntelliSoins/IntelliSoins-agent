#!/usr/bin/env bash
# PATCH ai-spark 2026-07-12 — watchdog : attend le retour SSH du Spark puis
# applique automatiquement les correctifs (task-102). Notification macOS à la fin.
# Usage : nohup ./wait-and-apply.sh > wait-and-apply.log 2>&1 &
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
INTERVAL=60
MAX_HOURS=24
DEADLINE=$(( $(date +%s) + MAX_HOURS*3600 ))

echo "[$(date '+%F %T')] Watchdog démarré (poll ${INTERVAL}s, max ${MAX_HOURS}h)"
while [[ $(date +%s) -lt $DEADLINE ]]; do
  if ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no spark 'echo SSH_OK' 2>/dev/null | grep -q SSH_OK; then
    echo "[$(date '+%F %T')] ✅ SSH Spark de retour — application des correctifs"
    if "$HERE/apply-spark-fixes.sh"; then
      osascript -e 'display notification "Correctifs sshd + preflight appliqués sur le Spark" with title "Spark récupéré ✅" sound name "Glass"' 2>/dev/null || true
      echo "[$(date '+%F %T')] ✅ Terminé avec succès"
    else
      osascript -e 'display notification "SSH revenu mais échec application — voir wait-and-apply.log" with title "Spark : correctifs en erreur ⚠️" sound name "Basso"' 2>/dev/null || true
      echo "[$(date '+%F %T')] ⚠️ apply-spark-fixes.sh a échoué"
    fi
    exit 0
  fi
  sleep "$INTERVAL"
done
echo "[$(date '+%F %T')] ⏰ Deadline ${MAX_HOURS}h atteinte — SSH jamais revenu"
osascript -e 'display notification "SSH Spark jamais revenu en 24h — reboot physique requis" with title "Spark toujours down ❌"' 2>/dev/null || true
exit 1
