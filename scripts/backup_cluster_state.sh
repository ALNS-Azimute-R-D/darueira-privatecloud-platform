#!/usr/bin/env bash
# ==============================================================================
# DARUEIRA PRIVATE CLOUD PLATFORM - BACKUP OF THE CLUSTER STATE THAT IS NOT IN A PV
#
# Complements scripts/backup_pvc.sh (which archives the persistent volumes). This one saves what lives
# only in the cluster or on the node:
#   k8s/        every Kubernetes object (all namespaces, Secrets included) as YAML, plus the CRDs;
#   postgres/   logical dumps (pg_dump -Fc + globals) of central-postgres and of both tenant-postgres,
#               portable across PostgreSQL versions and independent of the data directory format;
#   images/     the images that exist only in the node containerd cache (localhost:8082/*, never pushed to
#               Nexus), and the list of every image the cluster uses;
#   host/       MicroK8s versions/addons/args and the Docker daemon config (only what is readable);
#   MANIFEST.txt and SHA256SUMS.
#
# It is read-only for the cluster (kubectl get/exec, ctr export): no workload is stopped. Run it BEFORE
# `make backup-pvc` (which stops the workloads). The result CONTAINS SECRETS: the directory is created
# with mode 700 and the files with 600; encrypt it before copying it off this machine (see
# docs/runbooks/backup-and-disk-migration.md). Credentials are never put on a command line or printed:
# the dumps use the PG* environment of the database pod itself.
#
# Usage: scripts/backup_cluster_state.sh [--dest DIR]      (default DIR: ~/Backups/darueira-platform-state)
# ==============================================================================
set -euo pipefail
umask 077

KUBECTL="${KUBECTL:-kubectl}"
CTR="${CTR:-/snap/microk8s/current/bin/ctr --address /var/snap/microk8s/common/run/containerd.sock -n k8s.io}"
DEST="${BACKUP_STATE_DIR:-$HOME/Backups/darueira-platform-state}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dest) DEST="$2"; shift 2 ;;
    *) echo "Unknown argument: $1"; sed -n '2,24p' "$0"; exit 1 ;;
  esac
done

TS="$(date +%Y%m%d-%H%M%S)"
OUT="$DEST/$TS"
mkdir -p "$OUT"/{k8s,postgres,images,host}
chmod 700 "$DEST" "$OUT"
FAILED=()

log() { echo "==> $*"; }
warn() { echo "  [!] $*"; FAILED+=("$*"); }

# ---------------------------------------------------------------- 1. Kubernetes objects
SKIP='^(events|events\.events\.k8s\.io|endpoints|endpointslices\.discovery\.k8s\.io|pods|pods\.metrics\.k8s\.io|nodes\.metrics\.k8s\.io|replicasets\.apps|ciliumendpoints\.cilium\.io|ciliumidentities\.cilium\.io|ciliumendpointslices\.cilium\.io|componentstatuses)$'
log "Kubernetes objects (all namespaces, Secrets included)"
count=0
while read -r res; do
  [[ "$res" =~ $SKIP ]] && continue
  f="$OUT/k8s/${res}.yaml"
  if $KUBECTL get "$res" -A -o yaml > "$f" 2>/dev/null; then
    if grep -q '^items: \[\]' "$f"; then rm -f "$f"; else count=$((count + 1)); fi
  else
    rm -f "$f"
  fi
done < <($KUBECTL api-resources --verbs=list -o name)
echo "    $count resource kinds saved"
$KUBECTL get ns -o yaml > "$OUT/k8s/_namespaces.yaml"
$KUBECTL version -o yaml > "$OUT/k8s/_version.yaml" 2>/dev/null || true

# ---------------------------------------------------------------- 2. PostgreSQL logical dumps
dump_instance() {
  local label="$1" ns="$2" pod="$3" dbs db
  log "PostgreSQL $label ($ns/$pod)"
  mkdir -p "$OUT/postgres/$label"
  if ! dbs="$($KUBECTL -n "$ns" exec "$pod" -- sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U "$POSTGRES_USER" -d postgres -Atc "select datname from pg_database where not datistemplate"')"; then
    warn "$label: could not list databases"; return 0
  fi
  $KUBECTL -n "$ns" exec "$pod" -- sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dumpall -U "$POSTGRES_USER" --globals-only' \
    > "$OUT/postgres/$label/_globals.sql" || warn "$label: globals dump failed"
  while IFS= read -r db; do
    [ -n "$db" ] || continue
    if $KUBECTL -n "$ns" exec "$pod" -- sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -Fc -U "$POSTGRES_USER" -d "$1"' _ "$db" \
         > "$OUT/postgres/$label/$db.dump"; then
      echo "    $db: $(du -h "$OUT/postgres/$label/$db.dump" | cut -f1)"
    else
      warn "$label/$db: dump failed"
    fi
  done <<< "$dbs"
}
dump_instance central drr-corpshared-plat central-postgres-0
dump_instance swfabrik-europe drr-tnt-swfabrik-europe-dev tenant-postgres-0
dump_instance swfabrik-latam drr-tnt-swfabrik-latam-dev tenant-postgres-0

# ---------------------------------------------------------------- 3. Images only in the node cache
log "Images"
$KUBECTL get pods -A -o jsonpath='{range .items[*]}{range .spec.initContainers[*]}{.image}{"\n"}{end}{range .spec.containers[*]}{.image}{"\n"}{end}{end}' \
  | sort -u > "$OUT/images/images-in-use.txt"
echo "    $(wc -l < "$OUT/images/images-in-use.txt") images in use (list saved)"
mapfile -t LOCAL < <($CTR images ls -q 2>/dev/null | grep -E '^localhost:8082/' | grep -v '@sha256:' || true)
if [ "${#LOCAL[@]}" -gt 0 ]; then
  if $CTR images export "$OUT/images/node-local-images.tar" "${LOCAL[@]}" 2>/dev/null; then
    printf '%s\n' "${LOCAL[@]}" > "$OUT/images/node-local-images.txt"
    echo "    ${#LOCAL[@]} node-only images exported ($(du -h "$OUT/images/node-local-images.tar" | cut -f1))"
  else
    warn "images: ctr export failed (is the user in the microk8s group?)"
  fi
fi

# ---------------------------------------------------------------- 4. Host/MicroK8s configuration (only what is readable)
log "Host and MicroK8s configuration"
{ microk8s version; microk8s status --format short; } > "$OUT/host/microk8s-status.txt" 2>&1 || true
for f in /var/snap/microk8s/current/args /etc/docker/daemon.json /etc/fstab; do
  if [ -d "$f" ]; then cp -r "$f" "$OUT/host/$(basename "$f")" 2>/dev/null || true
  elif [ -r "$f" ]; then cp "$f" "$OUT/host/$(basename "$f")"
  else echo "    not readable (skipped): $f"; fi
done
{ lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT; df -hT; } > "$OUT/host/disks.txt" 2>&1 || true

# ---------------------------------------------------------------- 5. Manifest and checksums
{
  echo "Darueira cluster-state backup $TS"
  echo "Repo: $(git -C "$ROOT" rev-parse HEAD 2>/dev/null) ($(git -C "$ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null))"
  echo "Host: $(hostname)  Kernel: $(uname -r)"
  echo "Namespaces: $($KUBECTL get ns --no-headers | awk '{print $1}' | tr '\n' ' ')"
  echo "Failures: ${#FAILED[@]}"
  printf '  - %s\n' "${FAILED[@]}"
} > "$OUT/MANIFEST.txt"
(cd "$OUT" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
chmod -R go-rwx "$OUT"

log "Cluster-state backup written: $OUT ($(du -sh "$OUT" | cut -f1))"
if [ "${#FAILED[@]}" -gt 0 ]; then
  echo "  ${#FAILED[@]} step(s) failed, see MANIFEST.txt"; exit 2
fi
