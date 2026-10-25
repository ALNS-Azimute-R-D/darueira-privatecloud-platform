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
# Usage:  scripts/backup_pvc.sh backup [--dest DIR] [--include-nexus] [--include-obs] [--dry-run]
#         scripts/backup_pvc.sh list   [--dest DIR]
#         scripts/backup_pvc.sh verify [--dest DIR] [BACKUP_ID]
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

cmd="${1:-}"; shift || true
ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dest) DEST="$2"; shift 2 ;;
    --include-nexus) INCLUDE_NEXUS=1; shift ;;
    --include-obs) INCLUDE_OBS=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
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

cmd_backup() {
  local ts targets
  ts="$(date +%Y%m%d-%H%M%S)"
  out="$DEST/$ts"
  targets="$(discover_targets)"
  [ -n "$targets" ] || { echo "No volumes found"; exit 1; }

  declare -A WL_REPLICAS=()
  local lines=() ns claim rel kind name key
  while IFS='|' read -r ns claim rel kind name; do
    lines+=("$ns|$claim|$rel|$kind|$name")
    key="$ns|$kind|$name"
    [ "$kind" = "none" ] && continue
    if [ -z "${WL_REPLICAS[$key]:-}" ]; then
      WL_REPLICAS[$key]="$($KUBECTL get "$kind" "$name" -n "$ns" -o jsonpath='{.spec.replicas}')"
    fi
  done <<< "$targets"

  log "Volumes to back up (${#lines[@]}):"
  printf '    %s\n' "${lines[@]}"
  log "Workloads that will be scaled to 0 for the copy:"
  for key in "${!WL_REPLICAS[@]}"; do echo "    $key (replicas=${WL_REPLICAS[$key]})"; done
  [ "$DRY_RUN" = 1 ] && { log "Dry run, nothing changed"; return 0; }

  mkdir -p "$out"
  for key in "${!WL_REPLICAS[@]}"; do echo "${key}|${WL_REPLICAS[$key]}"; done > "$out/replicas.txt"

  restore_replicas() {
    trap - EXIT
    log "Restoring replicas (from $out/replicas.txt)"
    local order ns kd nm r
    # databases (StatefulSets) first, then the rest
    for order in StatefulSet Deployment; do
      while IFS='|' read -r ns kd nm r; do
        if [ "$kd" = "$order" ] && [ "$r" != "0" ]; then
          $KUBECTL scale "$kd/$nm" -n "$ns" --replicas="$r" >/dev/null && echo "  scaled $ns/$nm -> $r"
        fi
      done < "$out/replicas.txt"
    done
    $KUBECTL delete pod "$POD_NAME" -n "$POD_NS" --ignore-not-found >/dev/null 2>&1 || true
  }
  trap restore_replicas EXIT   # `out` must stay global: the trap runs after this function returned

  log "Scaling down"
  for key in "${!WL_REPLICAS[@]}"; do
    IFS='|' read -r ns kind name <<< "$key"
    $KUBECTL scale "$kind/$name" -n "$ns" --replicas=0 >/dev/null
  done
  for _ in $(seq 1 60); do
    busy=0
    for l in "${lines[@]}"; do
      IFS='|' read -r ns claim _ <<< "$l"
      if $KUBECTL get pods -n "$ns" -o json | jq -e --arg c "$claim" '.items[] | select(.spec.volumes[]?.persistentVolumeClaim.claimName == $c)' >/dev/null; then busy=1; fi
    done
    [ "$busy" = 0 ] && break
    sleep 3
  done
  [ "$busy" = 0 ] || { echo "Workloads did not stop in time"; exit 1; }

  log "Writing archives to $out"
  local script="set -eu; cd /data"
  for l in "${lines[@]}"; do
    IFS='|' read -r ns claim rel _ <<< "$l"
    script+="; tar --numeric-owner -czf \"/backup/${rel//\//__}.tar.gz\" \"$rel\""
  done
  script+="; cd /backup; sha256sum *.tar.gz > SHA256SUMS; chown -R $(id -u):$(id -g) /backup"

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
        - { name: data, mountPath: /data, readOnly: true }
        - { name: backup, mountPath: /backup }
  volumes:
    - name: data
      hostPath: { path: $DATA_ROOT }
    - name: backup
      hostPath: { path: $out }
EOF
  for _ in $(seq 1 600); do
    phase="$($KUBECTL get pod "$POD_NAME" -n "$POD_NS" -o jsonpath='{.status.phase}')"
    [ "$phase" = "Succeeded" ] && break
    [ "$phase" = "Failed" ] && { $KUBECTL logs "$POD_NAME" -n "$POD_NS" || true; echo "Backup pod failed"; exit 1; }
    sleep 3
  done
  [ "$phase" = "Succeeded" ] || { echo "Backup pod timed out"; exit 1; }
  log "Backup $ts written: $(du -sh "$out" | cut -f1)"
}

case "$cmd" in
  backup) cmd_backup ;;
  list) cmd_list ;;
  verify) cmd_verify ;;
  *) sed -n '2,24p' "$0"; exit 1 ;;
esac
