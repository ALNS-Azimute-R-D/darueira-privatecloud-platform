#!/usr/bin/env bash
# ==============================================================================
# DARUEIRA PRIVATE CLOUD PLATFORM - COLD BACKUP OF THE STATIC PERSISTENT VOLUMES
#
# Backs up every PV of the `darueira-host-storage` class (data under
# /mnt/FileBuckets01/darueira-platform/data) as one .tar.gz per volume.
#
# Cold means consistent: the workloads that mount the volumes are scaled to 0,
# the archives are written, and the previous replica counts are restored (also
# on error or Ctrl+C, through a trap). Reading the data dirs needs root because
# they belong to container UIDs, so the tar runs in a short-lived root pod with
# the data dir mounted read-only, which avoids needing sudo on the host.
#
# Skipped by default (rebuildable or large): nexus-data, prometheus-data,
# opensearch-data, grafana-data. Use --include-nexus / --include-obs.
# Never backed up: data/ephemeral (Tekton run workspaces).
#
# Restore: replaces the volume data with the archive contents. The current data dir is
# kept next to it as <dir>.pre-restore-<timestamp>, so a restore can be undone by hand.
# Workloads using the volumes are stopped first and brought back afterwards.
#
# Usage:  scripts/backup_pvc.sh backup  [--dest DIR] [--only TEXT] [--include-nexus] [--include-obs] [--dry-run]
#         scripts/backup_pvc.sh list    [--dest DIR]
#         scripts/backup_pvc.sh verify  [--dest DIR] [BACKUP_ID]
#         scripts/backup_pvc.sh restore [--dest DIR] BACKUP_ID [--only TEXT] [--yes]
#         scripts/backup_pvc.sh prune   [--dest DIR] --keep N
# --only keeps the volumes whose data path contains TEXT (e.g. forgejo, tenants/swfabrik-europe).
# ==============================================================================
set -euo pipefail

KUBECTL="${KUBECTL:-microk8s kubectl}"
DATA_ROOT="/mnt/FileBuckets01/darueira-platform/data"
DEST="${BACKUP_DIR:-$HOME/Backups/darueira-platform}"
POD_NS="kube-system"   # drr-* namespaces enforce PodSecurity baseline, which forbids hostPath
POD_NAME="drr-pvc-backup"
POD_IMAGE="postgres:17-alpine"
INCLUDE_NEXUS=0
INCLUDE_OBS=0
DRY_RUN=0
ONLY=""
ASSUME_YES=0
KEEP=0
RUN_DIR=""            # directory mounted at /backup in the helper pod
REPLICAS_DIR=""       # global: where the EXIT trap finds replicas.txt after the command function returned
declare -A WL_REPLICAS=()
LINES=()

cmd="${1:-}"; shift || true
ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dest) DEST="$2"; shift 2 ;;
    --include-nexus) INCLUDE_NEXUS=1; shift ;;
    --include-obs) INCLUDE_OBS=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --only) ONLY="$2"; shift 2 ;;
    --yes) ASSUME_YES=1; shift ;;
    --keep) KEEP="$2"; shift 2 ;;
    *) ARGS+=("$1"); shift ;;
  esac
done

log() { echo "==> $*"; }

cmd_list() {
  [ -d "$DEST" ] || { echo "No backups in $DEST"; return 0; }
  for d in "$DEST"/*/; do
    [ -f "${d}SHA256SUMS" ] || continue
    printf '%s  %s  %s volumes\n' "$(basename "$d")" "$(du -sh "$d" | cut -f1)" "$(ls "$d"*.tar.gz | wc -l)"
  done
}

cmd_verify() {
  local id="${ARGS[0]:-$(ls -1 "$DEST" 2>/dev/null | tail -1)}"
  [ -n "$id" ] && [ -d "$DEST/$id" ] || { echo "Backup not found"; exit 1; }
  log "Verifying $DEST/$id"
  (cd "$DEST/$id" && sha256sum -c SHA256SUMS && for f in *.tar.gz; do tar -tzf "$f" >/dev/null && echo "tar ok: $f"; done)
}

# Prints: ns|claim|relative-path|workload-kind|workload-name|replicas  (one line per volume)
discover_targets() {
  local tmp pvs rs
  tmp="$(mktemp)"; pvs="$(mktemp)"; rs="$(mktemp)"
  $KUBECTL get pv -o json > "$pvs"
  $KUBECTL get rs -A -o json > "$rs"
  $KUBECTL get pods -A -o json | jq -r --slurpfile pvs "$pvs" --slurpfile rs "$rs" --arg root "$DATA_ROOT/" \
    --argjson nexus "$INCLUDE_NEXUS" --argjson obs "$INCLUDE_OBS" '
    ($pvs[0].items | map(select(.spec.storageClassName == "darueira-host-storage" and .spec.claimRef != null))) as $pv
    | .items[] | . as $p
    | ($p.spec.volumes // [])[] | select(.persistentVolumeClaim != null) | .persistentVolumeClaim.claimName as $c
    | ($pv[] | select(.spec.claimRef.name == $c and .spec.claimRef.namespace == $p.metadata.namespace)) as $v
    | ($v.spec.hostPath.path | ltrimstr($root)) as $rel
    | select($rel | startswith("ephemeral") | not)
    | select(($nexus == 1) or ($rel | test("nexus-data") | not))
    | select(($obs == 1) or ($rel | test("^corpshared-obs/") | not))
    | ($p.metadata.ownerReferences // [{}])[0] as $o
    | (if $o.kind == "ReplicaSet"
         then ($rs[0].items[] | select(.metadata.name == $o.name and .metadata.namespace == $p.metadata.namespace) | .metadata.ownerReferences[0] | "Deployment|" + .name)
         else ($o.kind // "none") + "|" + ($o.name // "") end) as $w
    | "\($p.metadata.namespace)|\($c)|\($rel)|\($w)"' > "$tmp"
  # volumes without a running pod (e.g. MongoDB scaled to 0) are copied as-is
  jq -r --arg root "$DATA_ROOT/" --argjson nexus "$INCLUDE_NEXUS" --argjson obs "$INCLUDE_OBS" '
    .items[] | select(.spec.storageClassName == "darueira-host-storage" and .spec.claimRef != null)
    | (.spec.hostPath.path | ltrimstr($root)) as $rel
    | select($rel | startswith("ephemeral") | not)
    | select(($nexus == 1) or ($rel | test("nexus-data") | not))
    | select(($obs == 1) or ($rel | test("^corpshared-obs/") | not))
    | "\(.spec.claimRef.namespace)|\(.spec.claimRef.name)|\($rel)|none|"' "$pvs" | while IFS='|' read -r n c r k w; do
      grep -q "^$n|$c|$r|" "$tmp" || echo "$n|$c|$r|$k|$w" >> "$tmp"
    done
  sort -u "$tmp"; rm -f "$tmp" "$pvs" "$rs"
}

# Fills LINES (ns|claim|rel|kind|name) and WL_REPLICAS from the discovered volumes, honoring --only.
collect_lines() {
  local targets ns claim rel kind name key
  targets="$(discover_targets)"
  LINES=()
  while IFS='|' read -r ns claim rel kind name; do
    [ -n "$ns" ] || continue
    [ -z "$ONLY" ] || [[ "$rel" == *"$ONLY"* ]] || continue
    [ "$1" != "restore" ] || [ -f "$RUN_DIR/${rel//\//__}.tar.gz" ] || continue
    LINES+=("$ns|$claim|$rel|$kind|$name")
    key="$ns|$kind|$name"
    [ "$kind" = "none" ] && continue
    if [ -z "${WL_REPLICAS[$key]:-}" ]; then
      WL_REPLICAS[$key]="$($KUBECTL get "$kind" "$name" -n "$ns" -o jsonpath='{.spec.replicas}')"
    fi
  done <<< "$targets"
  [ "${#LINES[@]}" -gt 0 ] || { echo "No volumes matched"; exit 1; }
}

print_plan() {
  local key
  log "Volumes (${#LINES[@]}):"
  printf '    %s\n' "${LINES[@]}"
  log "Workloads that will be scaled to 0:"
  for key in "${!WL_REPLICAS[@]}"; do echo "    $key (replicas=${WL_REPLICAS[$key]})"; done
}

# Restores the replica counts saved in $REPLICAS_DIR/replicas.txt (StatefulSets first). Runs as the EXIT trap.
cold_start() {
  trap - EXIT
  [ -f "$REPLICAS_DIR/replicas.txt" ] || return 0
  log "Restoring replicas (from $REPLICAS_DIR/replicas.txt)"
  local order ns kd nm r
  for order in StatefulSet Deployment; do
    while IFS='|' read -r ns kd nm r; do
      if [ "$kd" = "$order" ] && [ "$r" != "0" ]; then
        $KUBECTL scale "$kd/$nm" -n "$ns" --replicas="$r" >/dev/null && echo "  scaled $ns/$nm -> $r"
      fi
    done < "$REPLICAS_DIR/replicas.txt"
  done
  $KUBECTL delete pod "$POD_NAME" -n "$POD_NS" --ignore-not-found >/dev/null 2>&1 || true
}

cold_stop() {
  local key ns claim busy=1 l kind name
  for key in "${!WL_REPLICAS[@]}"; do echo "${key}|${WL_REPLICAS[$key]}"; done > "$REPLICAS_DIR/replicas.txt"
  trap cold_start EXIT
  log "Scaling down"
  for key in "${!WL_REPLICAS[@]}"; do
    IFS='|' read -r ns kind name <<< "$key"
    $KUBECTL scale "$kind/$name" -n "$ns" --replicas=0 >/dev/null
  done
  for _ in $(seq 1 60); do
    busy=0
    for l in "${LINES[@]}"; do
      IFS='|' read -r ns claim _ <<< "$l"
      if $KUBECTL get pods -n "$ns" -o json | jq -e --arg c "$claim" '.items[] | select(.spec.volumes[]?.persistentVolumeClaim.claimName == $c)' >/dev/null; then busy=1; fi
    done
    [ "$busy" = 0 ] && break
    sleep 3
  done
  [ "$busy" = 0 ] || { echo "Workloads did not stop in time"; exit 1; }
}

# run_pod SCRIPT DATA_READONLY BACKUP_READONLY: runs SCRIPT as root with /data and /backup mounted.
run_pod() {
  local script="$1" data_ro="$2" backup_ro="$3" phase=""
  $KUBECTL delete pod "$POD_NAME" -n "$POD_NS" --ignore-not-found >/dev/null
  $KUBECTL apply -f - >/dev/null <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: $POD_NAME
  namespace: $POD_NS
spec:
  restartPolicy: Never
  containers:
    - name: tar
      image: $POD_IMAGE
      imagePullPolicy: IfNotPresent
      command: ["sh", "-c", '$script']
      securityContext:
        runAsUser: 0
      volumeMounts:
        - { name: data, mountPath: /data, readOnly: $data_ro }
        - { name: backup, mountPath: /backup, readOnly: $backup_ro }
  volumes:
    - name: data
      hostPath: { path: $DATA_ROOT }
    - name: backup
      hostPath: { path: $RUN_DIR }
EOF
  for _ in $(seq 1 1200); do
    phase="$($KUBECTL get pod "$POD_NAME" -n "$POD_NS" -o jsonpath='{.status.phase}')"
    [ "$phase" = "Succeeded" ] && break
    [ "$phase" = "Failed" ] && { $KUBECTL logs "$POD_NAME" -n "$POD_NS" || true; echo "Pod failed"; exit 1; }
    sleep 3
  done
  [ "$phase" = "Succeeded" ] || { echo "Pod timed out"; exit 1; }
  $KUBECTL logs "$POD_NAME" -n "$POD_NS" | sed 's/^/    /'
}

cmd_backup() {
  local ts l ns claim rel script
  ts="$(date +%Y%m%d-%H%M%S)"
  RUN_DIR="$DEST/$ts"
  collect_lines backup
  print_plan
  [ "$DRY_RUN" = 1 ] && { log "Dry run, nothing changed"; return 0; }

  mkdir -p "$RUN_DIR"; REPLICAS_DIR="$RUN_DIR"
  cold_stop

  log "Writing archives to $RUN_DIR"
  script="set -eu; cd /data"
  for l in "${LINES[@]}"; do
    IFS='|' read -r ns claim rel _ <<< "$l"
    script+="; tar --numeric-owner -czf \"/backup/${rel//\//__}.tar.gz\" \"$rel\""
  done
  script+="; cd /backup; sha256sum *.tar.gz > SHA256SUMS; chown -R $(id -u):$(id -g) /backup"
  run_pod "$script" true false
  log "Backup $ts written: $(du -sh "$RUN_DIR" | cut -f1)"
}

cmd_restore() {
  local id="${ARGS[0]:-}" ts l ns claim rel script
  [ -n "$id" ] && [ -d "$DEST/$id" ] || { echo "Usage: restore BACKUP_ID (see: list). Not found in $DEST"; exit 1; }
  RUN_DIR="$DEST/$id"
  ARGS=("$id"); cmd_verify
  collect_lines restore
  print_plan
  ts="$(date +%Y%m%d-%H%M%S)"
  log "Each current data dir will be kept as <dir>.pre-restore-$ts"
  [ "$DRY_RUN" = 1 ] && { log "Dry run, nothing changed"; return 0; }
  if [ "$ASSUME_YES" != 1 ]; then
    read -r -p "Replace the data of these volumes with backup $id? [type yes] " ans
    [ "$ans" = "yes" ] || { echo "Aborted"; exit 1; }
  fi

  # the replicas file of the backup must not be overwritten: keep the restore run's own copy elsewhere
  REPLICAS_DIR="$(mktemp -d)"
  cold_stop

  log "Restoring archives"
  script="set -eu; cd /data"
  for l in "${LINES[@]}"; do
    IFS='|' read -r ns claim rel _ <<< "$l"
    script+="; if [ -e \"$rel\" ]; then mv \"$rel\" \"$rel.pre-restore-$ts\"; fi; tar --numeric-owner -xzf \"/backup/${rel//\//__}.tar.gz\" -C /data; echo restored $rel"
  done
  run_pod "$script" false true
  log "Restore done. Previous data kept as *.pre-restore-$ts under $DATA_ROOT"
}

# Deletes all but the newest KEEP backups (only directories that contain SHA256SUMS count as backups).
cmd_prune() {
  [[ "$KEEP" =~ ^[1-9][0-9]*$ ]] || { echo "Usage: prune --keep N (N >= 1)"; exit 1; }
  local all=() old d
  for d in "$DEST"/*/; do [ -f "${d}SHA256SUMS" ] && all+=("$(basename "$d")"); done
  [ "${#all[@]}" -gt "$KEEP" ] || { log "Nothing to prune (${#all[@]} backups, keeping $KEEP)"; return 0; }
  for old in "${all[@]:0:${#all[@]}-KEEP}"; do
    log "Removing old backup $old"
    rm -rf "${DEST:?}/$old"
  done
}

case "$cmd" in
  prune) cmd_prune ;;
  backup) cmd_backup ;;
  list) cmd_list ;;
  verify) cmd_verify ;;
  restore) cmd_restore ;;
  *) sed -n '2,40p' "$0"; exit 1 ;;
esac
