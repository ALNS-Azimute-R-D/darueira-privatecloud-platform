#!/usr/bin/env bash
# ==============================================================================
# DARUEIRA PRIVATE CLOUD PLATFORM - CILIUM STALE ENDPOINT STATE CLEANUP (HOST)
#
# Problem: every `microk8s stop` (kill_all_container_shims = SIGKILL) and every
# node reboot kills all pod sandboxes without a CNI DEL. On the next start the
# Cilium 1.15 agent restores those dead endpoints from its state directory and
# keeps their IPs allocated ([restored] in `cilium status --verbose`), so the
# 10.1.0.0/24 pool leaks ~80 IPs per restart until pods hang in
# ContainerCreating with "range is full".
#
# Why not tmpfs: the MicroK8s containerd wrapper hardcodes
#   CILIUM_SOCK=${SNAP_DATA}/var/run/cilium/cilium.sock
# so the agent run dir cannot be moved, and a tmpfs would only be wiped on
# reboot, not on `microk8s stop/start` (which is what leaked on 2026-09-24).
#
# Fix: an ExecStartPre on snap.microk8s.daemon-containerd that wipes the Cilium
# endpoint state dirs ONLY when no MicroK8s pod shim survived, i.e. after a
# reboot or `microk8s stop`. A containerd-only restart (KillMode=process keeps
# the shims and pods alive) leaves the state untouched, so live endpoints are
# still restored as usual.
#
# Usage:  sudo scripts/setup_host_cilium_state_cleanup.sh            # install
#         sudo scripts/setup_host_cilium_state_cleanup.sh --uninstall
# Logs:   journalctl -t cilium-state-cleanup
# ==============================================================================
set -euo pipefail

CLEANUP_BIN="/usr/local/sbin/microk8s-cilium-stale-state-cleanup"
DROPIN_DIR="/etc/systemd/system/snap.microk8s.daemon-containerd.service.d"
DROPIN_FILE="${DROPIN_DIR}/10-cilium-stale-state-cleanup.conf"

if [[ "${EUID}" -ne 0 ]]; then
  echo "ERROR: run as root (sudo $0)" >&2
  exit 1
fi

if [[ "${1:-}" == "--uninstall" ]]; then
  rm -f "${DROPIN_FILE}" "${CLEANUP_BIN}"
  rmdir --ignore-fail-on-non-empty "${DROPIN_DIR}" 2>/dev/null || true
  systemctl daemon-reload
  echo "==> [Cilium State Cleanup] Uninstalled"
  exit 0
fi

echo "==> [Cilium State Cleanup] Installing ${CLEANUP_BIN}"
cat > "${CLEANUP_BIN}" <<'EOF'
#!/bin/sh
# Installed by darueira-privatecloud-platform/scripts/setup_host_cilium_state_cleanup.sh
# Runs as ExecStartPre of snap.microk8s.daemon-containerd. Must never fail the
# containerd start, hence the unconditional exit 0.
STATE_DIR="/var/snap/microk8s/current/var/run/cilium/state"
MICROK8S_SOCK="/var/snap/microk8s/common/run/containerd.sock"
TAG="cilium-state-cleanup"

# True if any MicroK8s pod shim is alive. Matches on the process name first
# (comm is truncated to "containerd-shim"), then on the MicroK8s containerd
# socket in its cmdline, so neither Docker's shims nor an unrelated process that
# merely has these strings in its arguments can fool the check.
microk8s_shims_running() {
  for pid in $(pgrep -x containerd-shim); do
    if tr '\0' ' ' < "/proc/${pid}/cmdline" 2>/dev/null | grep -q -- "-address ${MICROK8S_SOCK}"; then
      return 0
    fi
  done
  return 1
}

if microk8s_shims_running; then
  logger -t "${TAG}" "MicroK8s pod shims still running (containerd-only restart); keeping ${STATE_DIR}"
  exit 0
fi
if [ ! -d "${STATE_DIR}" ]; then
  exit 0
fi

# Endpoint state dirs are named by endpoint ID, optionally with a
# _next/_stale/_next_fail suffix. Everything else (templates, globals, ...) is
# node-level state the agent can reuse, so it is left alone.
COUNT=$(find "${STATE_DIR}" -mindepth 1 -maxdepth 1 -type d -regextype posix-extended \
          -regex '.*/[0-9]+(_next|_stale|_next_fail)?' | wc -l)
find "${STATE_DIR}" -mindepth 1 -maxdepth 1 -type d -regextype posix-extended \
     -regex '.*/[0-9]+(_next|_stale|_next_fail)?' -exec rm -rf {} + 2>/dev/null
logger -t "${TAG}" "No MicroK8s pod shims running (reboot or microk8s stop); removed ${COUNT} stale Cilium endpoint state dirs"
exit 0
EOF
chmod 0755 "${CLEANUP_BIN}"

echo "==> [Cilium State Cleanup] Installing systemd drop-in ${DROPIN_FILE}"
mkdir -p "${DROPIN_DIR}"
cat > "${DROPIN_FILE}" <<EOF
# Installed by darueira-privatecloud-platform/scripts/setup_host_cilium_state_cleanup.sh
[Service]
ExecStartPre=-${CLEANUP_BIN}
EOF
systemctl daemon-reload

echo "==> [Cilium State Cleanup] Done. Verify with:"
echo "    systemctl cat snap.microk8s.daemon-containerd.service | grep -A2 cilium"
echo "    journalctl -t cilium-state-cleanup   # after the next microk8s start"
