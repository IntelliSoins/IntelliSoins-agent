#!/usr/bin/env bash
# PATCH ai-spark 2026-07-12 — application des correctifs post-incident task-102.
# Idempotent. À lancer depuis le Mac quand SSH Spark répond de nouveau.
#   1. Drop-in systemd : sshd protégé OOM/mémoire/CPU (ssh.service + ssh@.service)
#   2. Déploie finetune-preflight.sh dans ~/ai-spark/ (additif, ne modifie PAS sparkctl)
#   3. Vérifications post-application
# L'intégration du preflight DANS sparkctl se fait manuellement après lecture
# du fichier réel (pas de patch à l'aveugle).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SPARK="spark"          # entrée ~/.ssh/config → intellisoins@10.0.0.5
SSH_OPTS=(-o ConnectTimeout=15 -o StrictHostKeyChecking=no)

echo "=== 1. Test SSH ==="
if ! ssh "${SSH_OPTS[@]}" "$SPARK" 'echo SSH_OK' 2>/dev/null | grep -q SSH_OK; then
  echo "❌ SSH Spark injoignable — rien appliqué." >&2
  exit 1
fi
echo "✅ SSH OK"

echo "=== 2. Drop-in systemd sshd ==="
scp "${SSH_OPTS[@]}" "$HERE/10-sshd-protection.conf" "$SPARK:/tmp/10-sshd-protection.conf"
ssh "${SSH_OPTS[@]}" "$SPARK" '
  set -e
  for unit in ssh.service ssh@.service; do
    sudo mkdir -p "/etc/systemd/system/${unit}.d"
    sudo cp /tmp/10-sshd-protection.conf "/etc/systemd/system/${unit}.d/10-sshd-protection.conf"
  done
  sudo systemctl daemon-reload
  # restart ssh : les connexions établies survivent
  sudo systemctl restart ssh || sudo systemctl restart sshd
  echo "--- vérification ---"
  systemctl show ssh -p OOMScoreAdjust -p MemoryMin -p CPUWeight 2>/dev/null \
    || systemctl show sshd -p OOMScoreAdjust -p MemoryMin -p CPUWeight
'

echo "=== 3. Déploiement finetune-preflight.sh ==="
scp "${SSH_OPTS[@]}" "$HERE/finetune-preflight.sh" "$SPARK:~/ai-spark/finetune-preflight.sh"
ssh "${SSH_OPTS[@]}" "$SPARK" 'chmod +x ~/ai-spark/finetune-preflight.sh && ~/ai-spark/finetune-preflight.sh --min-free-gb 1 && echo PREFLIGHT_SELFTEST_OK'

echo "=== 4. État général post-application ==="
ssh "${SSH_OPTS[@]}" "$SPARK" '
  echo "--- uptime ---"; uptime
  echo "--- mémoire ---"; free -h | head -3
  echo "--- containers ---"; docker ps --format "{{.Names}}: {{.Status}}"
  echo "--- FT en cours? ---"; docker ps --format "{{.Names}}" | grep -i finetune || echo "(aucun container finetune)"
'

cat <<'EOF'

✅ Correctifs appliqués.
RESTE À FAIRE MANUELLEMENT (après lecture du sparkctl réel) :
  - intégrer le preflight dans `sparkctl finetune start` :
      ~/ai-spark/finetune-preflight.sh --min-free-gb 60 || exit 1
  - exposer tensorboard sur sparklan si suivi FT voulu (lien Michael)
EOF
