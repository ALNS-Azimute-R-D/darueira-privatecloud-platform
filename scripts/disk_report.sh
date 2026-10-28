#!/usr/bin/env bash
# ==============================================================================
# DARUEIRA PRIVATE CLOUD PLATFORM - READ-ONLY DISK REPORT
#
# One screen of where the disk space goes: filesystem usage, the platform data
# tree by tier, backups, host logs, MicroK8s/containerd and the usual developer
# caches. Nothing is deleted or changed; candidates are only grouped by how safe
# they are to clean ("regenerable cache" vs "needs a human decision").
#
# Every path is measured with `du` in parallel, at idle I/O priority, with a
# per-path timeout, so a slow directory shows "timeout" instead of blocking the
# whole report. Honest sizes only:
#   timeout            du did not finish; rerun with a larger --timeout
#   >= 1,4G (partial)  some subdirectories are unreadable (root-owned): the real
#                      size is larger. Run the report with sudo for exact values.
#
# Usage:  scripts/disk_report.sh [--timeout SECONDS] [--jobs N] [--deep]
#   --timeout S   per-path limit in seconds                          (default 25)
#   --jobs N      parallel du processes                              (default 6)
#   --deep        also break down the top level of $HOME (slower)
# ==============================================================================
set -uo pipefail

DATA_ROOT="${DRR_DATA_ROOT:-/mnt/FileBuckets01/darueira-platform}"
BACKUP_ROOT="${BACKUP_DIR:-$HOME/Backups/darueira-platform}"
TIMEOUT=25
JOBS=6
DEEP=0
WARN_PCT=80

while [[ $# -gt 0 ]]; do
  case "$1" in
    --deep) DEEP=1; shift ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --jobs) JOBS="$2"; shift 2 ;;
    -h|--help) sed -n 2,21p "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done

CYAN=$'\033[0;36m'; YELLOW=$'\033[1;33m'; NC=$'\033[0m'
[[ -t 1 ]] || { CYAN=""; YELLOW=""; NC=""; }

CACHE=$(mktemp -d)
trap 'rm -rf "$CACHE"' EXIT

key() { printf '%s' "$1" | md5sum | cut -d' ' -f1; }

# measure_one PATH -> writes "<du exit code>|<human size>" to the cache
measure_one() {
  local p="$1" out rc
  out=$(timeout "$TIMEOUT" ionice -c3 du -sxh "$p" 2>/dev/null); rc=$?
  printf '%s|%s\n' "$rc" "$(printf '%s\n' "$out" | tail -1 | cut -f1)" > "$CACHE/$(key "$p")"
}
export -f measure_one key
export CACHE TIMEOUT

# size_of PATH -> human readable, honest about partial results
size_of() {
  local p="$1" rc size
  [[ -e "$p" ]] || { echo "-"; return; }
  IFS='|' read -r rc size < "$CACHE/$(key "$p")" 2>/dev/null || { echo "n/a"; return; }
  case "$rc" in
    0)   echo "$size" ;;
    124) echo "timeout (>${TIMEOUT}s)" ;;
    *)   [[ -n "$size" ]] && echo ">= $size (partial, needs sudo)" || echo "n/a (needs sudo)" ;;
  esac
}

row() { printf '  %-46s %s\n' "$1" "$2"; }
section() { printf '\n%s== %s ==%s\n' "$CYAN" "$1" "$NC"; }

# ---- collect every path first, measure them all in parallel -----------------
PATHS=()
add() { for p in "$@"; do [[ -e "$p" ]] && PATHS+=("$p"); done; }

add "$DATA_ROOT"/data/*/ "$DATA_ROOT"/data/*/*/ "$BACKUP_ROOT" "$BACKUP_ROOT"/*/
add /var/log /var/log/pods /var/log/journal /var/snap/microk8s \
    /var/snap/microk8s/common/default-storage /var/snap/microk8s/common/var/lib/containerd
CACHES=("$HOME/.m2" "$HOME/.gradle" "$HOME/.npm" "$HOME/.cache" "$HOME/.config/JetBrains" "$HOME/.cache/JetBrains")
LEFTOVERS=("$HOME/.docker" "$HOME/.local/share/containers" "$HOME/.local/share/Trash")
HOMEDIRS=(DevEnvALNS Backups VirtualMachines Downloads Documents .local .thunderbird .android)
add "${CACHES[@]}" "${LEFTOVERS[@]}"
for d in "${HOMEDIRS[@]}"; do add "$HOME/$d"; done
if [[ $DEEP -eq 1 ]]; then
  while IFS= read -r d; do PATHS+=("$d"); done < <(find "$HOME" -mindepth 1 -maxdepth 1 -type d 2>/dev/null)
fi

printf '%s\n' "${PATHS[@]}" | sort -u | xargs -r -d '\n' -P "$JOBS" -I{} bash -c 'measure_one "$1"' _ {}

# ---- report -----------------------------------------------------------------
section "Filesystems"
printf '  %-28s %7s %7s %7s %5s\n' "mount" "size" "used" "avail" "use%"
for m in / /home /mnt/FileBuckets01; do
  mountpoint -q "$m" 2>/dev/null || [[ "$m" == "/" ]] || continue
  read -r size used avail pct < <(df -h --output=size,used,avail,pcent "$m" | tail -1)
  flag=""; [[ "${pct%\%}" -ge "$WARN_PCT" ]] && flag="  ${YELLOW}<- at or above ${WARN_PCT}%${NC}"
  printf '  %-28s %7s %7s %7s %5s%s\n' "$m" "$size" "$used" "$avail" "$pct" "$flag"
done

section "Platform data tree ($DATA_ROOT/data)"
if [[ -d "$DATA_ROOT/data" ]]; then
  for d in "$DATA_ROOT"/data/*/; do row "data/$(basename "$d")/" "$(size_of "$d")"; done
  echo "  -- largest volumes:"
  for v in "$DATA_ROOT"/data/*/*/; do
    IFS='|' read -r _ raw < "$CACHE/$(key "$v")" 2>/dev/null || raw=""
    printf '%s\t%s\t%s\n' "${raw:-0}" "data/${v#"$DATA_ROOT"/data/}" "$(size_of "$v")"
  done | sort -t$'\t' -k1,1 -rh | head -7 | awk -F'\t' '{ printf "  %-46s %s\n", $2, $3 }'
else
  echo "  not found: $DATA_ROOT/data"
fi

section "Backups ($BACKUP_ROOT)"
if [[ -d "$BACKUP_ROOT" ]]; then
  row "total" "$(size_of "$BACKUP_ROOT")"
  for d in "$BACKUP_ROOT"/*/; do row "  $(basename "$d")" "$(size_of "$d")"; done
  last=$(find "$BACKUP_ROOT" -maxdepth 1 -mindepth 1 -type d -name '2*' 2>/dev/null | sort | tail -1)
  [[ -n "$last" ]] && row "newest backup" "$(basename "$last") ($(( ( $(date +%s) - $(stat -c %Y "$last") ) / 86400 )) days old)"
  case "$BACKUP_ROOT" in
    /home/*) echo "  ${YELLOW}note: backups are on the same disk as /home; an off-disk copy is still needed${NC}" ;;
  esac
else
  echo "  not found: $BACKUP_ROOT"
fi

section "Host logs and MicroK8s (parts are root-owned)"
row "/var/log" "$(size_of /var/log)"
row "  /var/log/pods" "$(size_of /var/log/pods)"
row "  /var/log/journal" "$(size_of /var/log/journal)"
command -v journalctl >/dev/null 2>&1 && row "  journald (as reported by journalctl)" "$(journalctl --disk-usage 2>/dev/null | grep -oE '[0-9.]+[KMGT]' | head -1 || echo n/a)"
row "/var/snap/microk8s" "$(size_of /var/snap/microk8s)"
row "  common/default-storage (dynamic PVs)" "$(size_of /var/snap/microk8s/common/default-storage)"
row "  common/var/lib/containerd (images)" "$(size_of /var/snap/microk8s/common/var/lib/containerd)"

section "Regenerable caches (safe to delete; they refill on demand)"
for p in "${CACHES[@]}"; do [[ -e "$p" ]] && row "${p/#$HOME/~}" "$(size_of "$p")"; done

section "Container leftovers and trash (decide before cleaning)"
for p in "${LEFTOVERS[@]}"; do [[ -e "$p" ]] && row "${p/#$HOME/~}" "$(size_of "$p")"; done
command -v docker >/dev/null 2>&1 && row "docker containers running" "$(docker ps -q 2>/dev/null | wc -l)"

section "/home top level (needs a human decision per item)"
if [[ $DEEP -eq 1 ]]; then
  for d in $(find "$HOME" -mindepth 1 -maxdepth 1 -type d 2>/dev/null); do
    printf '%s\t%s\n' "$(size_of "$d")" "${d/#$HOME/~}"
  done | sort -rh | head -16 | awk -F'\t' '{ printf "  %-46s %s\n", $2, $1 }'
else
  for d in "${HOMEDIRS[@]}"; do [[ -e "$HOME/$d" ]] && row "~/$d" "$(size_of "$HOME/$d")"; done
  echo "  (--deep lists every top-level directory; raise --timeout for the big ones)"
fi

section "Next steps (manual, nothing was changed)"
echo "  - Caches above are safe candidates; move to a staging dir first, delete later."
echo "  - Backups, Documents, VirtualMachines, DevEnvALNS: decide item by item."
echo "  - Root-owned logs: sudo journalctl --vacuum-size=500M"
echo "  - Exact sizes for root-owned paths: sudo scripts/disk_report.sh"
