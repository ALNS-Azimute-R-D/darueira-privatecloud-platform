#!/usr/bin/env bash
# Unattended wrapper for the systemd timer: cold backup, verify, then prune old backups.
# Skips (exit 0) when the cluster is down or a CI run is active, so a missed or unlucky slot is harmless.
# Env: BACKUP_KEEP (default 4), BACKUP_DIR (default ~/Backups/darueira-platform).
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="${BACKUP_DIR:-$HOME/Backups/darueira-platform}"
KEEP="${BACKUP_KEEP:-4}"
KUBECTL="${KUBECTL:-microk8s kubectl}"
mkdir -p "$DEST"
exec >> "$DEST/backup.log" 2>&1
echo "##### $(date -Is) scheduled backup"

if ! timeout 20 $KUBECTL get nodes >/dev/null 2>&1; then
  echo "skip: cluster is not reachable"; exit 0
fi
if [ -n "$($KUBECTL get pipelinerun -n drr-corpshared-mgmt --no-headers 2>/dev/null | grep -iE 'running|started|pending')" ]; then
  echo "skip: a CI run is active"; exit 0
fi
unready="$($KUBECTL get pods -A --no-headers | grep '^drr-' | awk '{split($3,a,"/"); if(($4!="Running"&&$4!="Completed")||(a[1]!=a[2]&&$4=="Running")) c++} END{print c+0}')"
if [ "$unready" != "0" ]; then
  echo "skip: $unready pods are not ready (stopping workloads now could hide a problem)"; exit 0
fi

BACKUP_DIR="$DEST" "$HERE/backup_pvc.sh" backup || { echo "FAILED: backup"; exit 1; }
BACKUP_DIR="$DEST" "$HERE/backup_pvc.sh" verify >/dev/null || { echo "FAILED: verify, not pruning"; exit 1; }
BACKUP_DIR="$DEST" "$HERE/backup_pvc.sh" prune --keep "$KEEP"
echo "done"
