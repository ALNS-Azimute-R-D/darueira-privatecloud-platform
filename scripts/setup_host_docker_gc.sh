#!/usr/bin/env bash
# ==============================================================================
# DARUEIRA PRIVATE CLOUD PLATFORM - DOCKER BUILD CACHE GARBAGE COLLECTION (HOST)
#
# Problem: the system Docker daemon (/var/lib/docker, on /) had no build cache
# garbage collection. The `builder.gc.defaultKeepStorage` that existed lived in
# ~/.docker/daemon.json, which only Docker Desktop reads, so the cache grew to
# 110 GB (2026-10-28) until it was pruned by hand.
#
# Fix: set `builder.gc` in /etc/docker/daemon.json (merged into the existing
# file, every other key is preserved) so BuildKit keeps at most KEEP of cache.
# This only affects Docker. MicroK8s uses its own containerd, and the cluster
# builds with Kaniko, so nothing in the cluster depends on it.
#
# Safe by default: without --apply it only prints the resulting file and a diff
# and changes nothing (no root needed). With --apply (needs root) it:
#   1. refuses to continue if any container is running (the restart would stop it),
#      unless --force is given;
#   2. backs up the current file as /etc/docker/daemon.json.bak-<timestamp>;
#   3. validates the new file with `dockerd --validate`;
#   4. installs it and restarts docker, then checks the daemon came back.
#
# Usage:  scripts/setup_host_docker_gc.sh [--keep 20GB]                 # dry run
#         sudo scripts/setup_host_docker_gc.sh --apply [--keep 20GB] [--force]
# Rollback: sudo cp /etc/docker/daemon.json.bak-<timestamp> /etc/docker/daemon.json \
#             && sudo systemctl restart docker
# ==============================================================================
set -euo pipefail

CONFIG="/etc/docker/daemon.json"
KEEP="20GB"
APPLY=0
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --force) FORCE=1; shift ;;
    --keep) KEEP="$2"; shift 2 ;;
    -h|--help) sed -n 2,28p "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done

[[ "$KEEP" =~ ^[0-9]+(KB|MB|GB|TB)$ ]] || { echo "invalid --keep '$KEEP' (examples: 20GB, 500MB)" >&2; exit 1; }

NEW=$(mktemp)
trap 'rm -f "$NEW"' EXIT

# Merge: keep every existing key, set builder.gc.enabled and builder.gc.defaultKeepStorage.
CONFIG="$CONFIG" KEEP="$KEEP" python3 - > "$NEW" <<'PY'
import json, os
path, keep = os.environ["CONFIG"], os.environ["KEEP"]
try:
    with open(path) as f:
        cfg = json.load(f)
except FileNotFoundError:
    cfg = {}
gc = cfg.setdefault("builder", {}).setdefault("gc", {})
gc["enabled"] = True
gc["defaultKeepStorage"] = keep
print(json.dumps(cfg, indent=4))
PY

echo "==> Resulting $CONFIG (builder.gc keeps at most $KEEP of build cache):"
cat "$NEW"
echo
echo "==> Diff against the current file:"
diff -u "$CONFIG" "$NEW" || true
echo

if [[ $APPLY -eq 0 ]]; then
  echo "Dry run: nothing was changed. Run with: sudo $0 --apply --keep $KEEP"
  exit 0
fi

[[ $EUID -eq 0 ]] || { echo "--apply needs root: sudo $0 --apply" >&2; exit 1; }

running=$(docker ps -q | wc -l)
if [[ "$running" -gt 0 && $FORCE -eq 0 ]]; then
  echo "$running container(s) running; restarting docker would stop them. Stop them first or use --force." >&2
  exit 1
fi

if [[ -f "$CONFIG" ]]; then
  BACKUP="$CONFIG.bak-$(date +%Y%m%d-%H%M%S)"
  cp -p "$CONFIG" "$BACKUP"
  echo "==> Backup: $BACKUP"
fi

dockerd --validate --config-file="$NEW"
install -m 0644 -o root -g root "$NEW" "$CONFIG"
echo "==> Installed $CONFIG, restarting docker..."
systemctl restart docker

for _ in $(seq 1 20); do
  docker info >/dev/null 2>&1 && break
  sleep 1
done
docker info >/dev/null 2>&1 || { echo "docker did not come back; roll back with the backup above" >&2; exit 1; }
echo "==> docker is up. Build cache now:"
docker system df | sed -n '1p;/Build Cache/p'
