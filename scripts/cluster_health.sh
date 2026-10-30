#!/usr/bin/env bash
# ==============================================================================
# DARUEIRA PRIVATE CLOUD PLATFORM - READ-ONLY CLUSTER HEALTH CHECK
#
# One-shot summary of what is wrong right now: node pressure, pods that are not
# running, recent restarts, deployments below their desired replicas, PVCs/PVs in
# a bad state, ArgoCD applications out of sync, images that are not pinned (a
# restart re-pulls `:latest`), TLS secrets close to expiry and stale Cilium
# endpoints (the IPAM leak fixed on 2026-09-24).
#
# Read-only: it only runs `kubectl get/top`. Exit code: 0 = no findings,
# 1 = findings (warnings), 2 = cluster not reachable.
#
# Usage:  scripts/cluster_health.sh [--restarts N] [--top N] [--recent-hours H] [--cert-days D]
#   --restarts N       count pods whose restart count is >= N           (default 20)
#   --top N            how many of those to list                        (default 10)
#   --recent-hours H   a restart in the last H hours counts as recent   (default 24)
#   --cert-days D      warn when a TLS secret expires within D days     (default 30)
# ==============================================================================
set -uo pipefail

KUBECTL="${KUBECTL:-microk8s kubectl}"
RESTARTS=20
TOP=10
RECENT_HOURS=24
CERT_DAYS=30

while [[ $# -gt 0 ]]; do
  case "$1" in
    --restarts) RESTARTS="$2"; shift 2 ;;
    --top) TOP="$2"; shift 2 ;;
    --recent-hours) RECENT_HOURS="$2"; shift 2 ;;
    --cert-days) CERT_DAYS="$2"; shift 2 ;;
    -h|--help) sed -n 2,19p "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

if ! timeout 20 $KUBECTL get nodes -o json > "$TMP/nodes.json" 2>/dev/null; then
  echo "Cluster not reachable (is MicroK8s running? try: microk8s status)" >&2
  exit 2
fi

get() { timeout 40 $KUBECTL get "$@" -A -o json > "$TMP/$1.json" 2>/dev/null || echo '{"items":[]}' > "$TMP/$1.json"; }
get pods; get deployments; get statefulsets; get pvc; get applications.argoproj.io
mv "$TMP/applications.argoproj.io.json" "$TMP/apps.json"
get ciliumendpoints.cilium.io; mv "$TMP/ciliumendpoints.cilium.io.json" "$TMP/ceps.json"
timeout 40 $KUBECTL get pv -o json > "$TMP/pv.json" 2>/dev/null || echo '{"items":[]}' > "$TMP/pv.json"
timeout 40 $KUBECTL get secrets -A --field-selector type=kubernetes.io/tls -o json > "$TMP/tls.json" 2>/dev/null || echo '{"items":[]}' > "$TMP/tls.json"
timeout 20 $KUBECTL top node --no-headers > "$TMP/top.txt" 2>/dev/null || : > "$TMP/top.txt"

TMPDIR_HEALTH="$TMP" RESTARTS="$RESTARTS" TOP="$TOP" RECENT_HOURS="$RECENT_HOURS" CERT_DAYS="$CERT_DAYS" \
python3 - <<'PY'
import base64, json, os, subprocess, sys
from datetime import datetime, timedelta, timezone

T = os.environ["TMPDIR_HEALTH"]
RESTARTS = int(os.environ["RESTARTS"]); TOP = int(os.environ["TOP"]); RECENT = int(os.environ["RECENT_HOURS"]); CERT_DAYS = int(os.environ["CERT_DAYS"])
now = datetime.now(timezone.utc)
tty = sys.stdout.isatty()
C = {"h": "\033[0;36m", "w": "\033[1;33m", "ok": "\033[0;32m", "n": "\033[0m"} if tty else {k: "" for k in ("h", "w", "ok", "n")}
findings = 0

def load(name):
    with open(f"{T}/{name}.json") as f:
        return json.load(f)["items"]

def section(title, lines, ok_text="ok"):
    global findings
    print(f"\n{C['h']}== {title} =={C['n']}")
    if lines:
        findings += len(lines)
        for l in lines:
            print(f"  {C['w']}!{C['n']} {l}")
    else:
        print(f"  {C['ok']}{ok_text}{C['n']}")

def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None

# --- Node ---------------------------------------------------------------
lines = []
top = "metrics unavailable"
for n in load("nodes"):
    conds = {c["type"]: c["status"] for c in n["status"]["conditions"]}
    if conds.get("Ready") != "True": lines.append(f"node {n['metadata']['name']} is not Ready")
    for k in ("MemoryPressure", "DiskPressure", "PIDPressure"):
        if conds.get(k) == "True": lines.append(f"node {n['metadata']['name']}: {k}")
try:
    for l in open(f"{T}/top.txt").read().splitlines():
        p = l.split()
        if len(p) >= 5:
            for label, val in (("cpu", p[2]), ("memory", p[4])):
                if int(val.rstrip("%")) >= 85: lines.append(f"node {p[0]}: {label} at {val}")
            top = f"cpu {p[2]}, memory {p[4]} ({p[3]})"
except Exception:
    pass
section(f"Node ({top})", lines)

# --- Pods ---------------------------------------------------------------
pods = load("pods")
bad, recent, hist = [], [], {}
for p in pods:
    ns, name = p["metadata"]["namespace"], p["metadata"]["name"]
    phase = p["status"].get("phase")
    if phase == "Succeeded": continue
    main = p["status"].get("containerStatuses", [])
    css = main + p["status"].get("initContainerStatuses", [])
    owners = {o.get("kind") for o in p["metadata"].get("ownerReferences", [])}
    waiting = [c["state"]["waiting"]["reason"] for c in css if "waiting" in c.get("state", {})]
    not_ready = [c["name"] for c in main if not c.get("ready")]
    if (phase != "Running" or waiting or not_ready) and "Job" not in owners:
        bad.append(f"{ns}/{name}: phase={phase} waiting={waiting or '-'} notReady={not_ready or '-'}")
    worst = 0
    for c in main:
        rc = c.get("restartCount", 0)
        last = (c.get("lastState") or {}).get("terminated")
        when = ts(last.get("finishedAt")) if last else None
        if when and now - when <= timedelta(hours=RECENT):
            recent.append((when, f"{ns}/{name}/{c['name']}: exit {last.get('reason')}/{last.get('exitCode')} at {when:%m-%d %H:%MZ} (restarts={rc})"))
        worst = max(worst, rc)
    if worst >= RESTARTS:
        hist[f"{ns}/{name}"] = worst
section("Pods not running or not ready (Job pods in progress ignored)", sorted(bad))

# Restarts that happen together are a cluster start/stop, not a fault: collapse the biggest 15-minute burst.
recent.sort()
burst = []
for i, (t0, _) in enumerate(recent):
    group = [r for r in recent[i:] if r[0] - t0 <= timedelta(minutes=15)]
    if len(group) > len(burst): burst = group
lines = []
if len(burst) >= 8:
    lines_burst = f"{len(burst)} containers restarted within 15 min ({burst[0][0]:%m-%d %H:%MZ} to {burst[-1][0]:%H:%MZ}): looks like a cluster start/stop, not a fault"
    recent = [r for r in recent if r not in burst]
    lines.append(lines_burst)
lines += [r[1] for r in recent]
section(f"Containers that restarted in the last {RECENT}h", lines)
top_hist = sorted(hist.items(), key=lambda kv: -kv[1])
lines = [f"{k}: {v} restarts" for k, v in top_hist[:TOP]]
if len(top_hist) > TOP: lines.append(f"... and {len(top_hist) - TOP} more pods with >= {RESTARTS} restarts (use --top {len(top_hist)} to list)")
section(f"Pods with >= {RESTARTS} restarts in total (historical, top {TOP})", lines)

# --- Workloads ----------------------------------------------------------
lines = []
for kind in ("deployments", "statefulsets"):
    for w in load(kind):
        want = w["spec"].get("replicas", 1)
        have = w["status"].get("readyReplicas", 0)
        if want and have < want:
            lines.append(f"{kind[:-1]} {w['metadata']['namespace']}/{w['metadata']['name']}: ready {have}/{want}")
section("Workloads below desired replicas (scaled-to-zero ones are ignored)", sorted(lines))

# --- Storage ------------------------------------------------------------
lines = []
for c in load("pvc"):
    if c["status"].get("phase") != "Bound":
        lines.append(f"pvc {c['metadata']['namespace']}/{c['metadata']['name']}: {c['status'].get('phase')}")
for v in load("pv"):
    if v["status"].get("phase") in ("Released", "Failed"):
        ref = v["spec"].get("claimRef") or {}
        lines.append(f"pv {v['metadata']['name']}: {v['status']['phase']} (claim {ref.get('namespace', '-')}/{ref.get('name', '-')})")
section("Storage (PVC not Bound, PV Released/Failed)", sorted(lines))

# --- ArgoCD ---------------------------------------------------------------
lines = []
for a in load("apps"):
    sync = a.get("status", {}).get("sync", {}).get("status")
    health = a.get("status", {}).get("health", {}).get("status")
    if sync != "Synced" or health != "Healthy":
        lines.append(f"app {a['metadata']['name']}: sync={sync} health={health}")
section("ArgoCD applications", sorted(lines), "all Synced/Healthy")

# --- Unpinned images --------------------------------------------------------
unpinned = {}
for p in pods:
    spec = p["spec"]
    for c in spec.get("containers", []) + spec.get("initContainers", []):
        img = c["image"]
        last = img.rsplit("/", 1)[-1]
        if "@sha256:" in img: continue
        if ":" not in last or last.endswith(":latest"):
            unpinned.setdefault(img, set()).add(p["metadata"]["namespace"])
lines = [f"{img} (namespaces: {', '.join(sorted(ns))})" for img, ns in sorted(unpinned.items())]
section("Images not pinned (a restart re-pulls them; see the Stalwart v1.0.0 incident, 2026-10-27)", lines)

# --- TLS secrets --------------------------------------------------------------
lines = []
for s in load("tls"):
    crt = (s.get("data") or {}).get("tls.crt")
    if not crt: continue
    try:
        out = subprocess.run(["openssl", "x509", "-noout", "-enddate"], input=base64.b64decode(crt),
                             capture_output=True, timeout=10).stdout.decode()
        end = datetime.strptime(out.strip().split("=")[1], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    except Exception:
        continue
    days = (end - now).days
    if days <= CERT_DAYS:
        lines.append(f"tls secret {s['metadata']['namespace']}/{s['metadata']['name']}: "
                     + (f"EXPIRED {-days} days ago" if days < 0 else f"expires in {days} days ({end:%Y-%m-%d})"))
section(f"TLS secrets expiring within {CERT_DAYS} days", sorted(lines))

# --- Cilium endpoints -----------------------------------------------------------
pod_keys = {(p["metadata"]["namespace"], p["metadata"]["name"]) for p in pods}
ceps = load("ceps")
stale = [f"{c['metadata']['namespace']}/{c['metadata']['name']}" for c in ceps
         if (c["metadata"]["namespace"], c["metadata"]["name"]) not in pod_keys]
lines = [f"{len(ceps)} CiliumEndpoints for {len(pods)} pods (pod CIDR /24 holds 254 addresses)"] if len(ceps) >= 200 else []
lines += [f"stale CiliumEndpoint without a pod: {s}" for s in sorted(stale)[:10]]
if len(stale) > 10: lines.append(f"... and {len(stale) - 10} more stale endpoints")
section("Cilium endpoints / IPAM", lines)

print(f"\n{C['h']}Summary:{C['n']} {findings} finding(s)." + ("" if findings else " Cluster looks healthy."))
sys.exit(1 if findings else 0)
PY
