#!/usr/bin/env python3
"""
Create / update the NiFi "BookAnything - GeoLocation Cleanup Pipeline" process group from
platform/nifi/bookanything-geolocation-cleanup/flow.json (ADR-0015), so the flow is code in the repository
instead of edits made in the NiFi UI.

Idempotent:
  --check   (default) compares the file with the live flow and reports what would change; changes nothing
  --apply   creates the missing group, processors and connections, updates the ones that drifted
            (stop -> update -> start) and starts everything

It only ever touches the cleanup process group; the import pipeline is never modified.

Auth: mTLS with the node keystore from inside the apache-nifi pod (same as scripts/apply_nifi_script_body.py).
Secrets: `{{CENTRAL_MINIO_ACCESS_KEY}}` / `{{CENTRAL_MINIO_SECRET_KEY}}` in flow.json are resolved from the
environment of the central-minio pod at apply time and are never printed or stored.
"""
import argparse
import json
import pathlib
import subprocess
import sys
import time

NAMESPACE = "drr-corpshared-plat"
DEPLOYMENT = "deploy/apache-nifi"
API = "https://localhost:8443/nifi-api"
CERT = "/opt/nifi/certs/keystore.p12:darueira-keystore-pass"
FLOW_DIR = pathlib.Path(__file__).resolve().parent.parent / "platform/nifi/bookanything-geolocation-cleanup"
BUNDLE_GROUP = "org.apache.nifi"
BUNDLE_VERSION = "1.28.1"
SENSITIVE = {"Access Key", "Secret Key"}


def nifi(method, path, body=None):
    cmd = ["kubectl", "-n", NAMESPACE, "exec", "-i", DEPLOYMENT, "-c", "nifi", "--",
           "curl", "-sk", "--cert-type", "P12", "--cert", CERT,
           "-X", method, "-w", "\n%{http_code}", f"{API}{path}"]
    stdin = None
    if body is not None:
        cmd[-1:-1] = ["-H", "Content-Type: application/json", "--data-binary", "@-"]
        stdin = json.dumps(body)
    out = subprocess.run(cmd, input=stdin, capture_output=True, text=True, check=True).stdout
    text, _, code = out.rpartition("\n")
    if not code.startswith("2"):
        raise RuntimeError(f"{method} {path} -> HTTP {code}: {text[:500]}")
    return json.loads(text) if text.strip() else {}


def minio_credentials():
    out = subprocess.run(
        ["kubectl", "-n", NAMESPACE, "exec", "deploy/central-minio", "-c", "minio", "--",
         "sh", "-c", 'printf "%s\\n%s" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"'],
        capture_output=True, text=True, check=True).stdout.split("\n")
    if len(out) < 2 or not out[0] or not out[1]:
        sys.exit("ERROR: could not read the central MinIO credentials from its pod")
    return {"CENTRAL_MINIO_ACCESS_KEY": out[0], "CENTRAL_MINIO_SECRET_KEY": out[1]}


def resolve(properties, secrets):
    """Placeholders -> values. Returns (properties, names of the sensitive ones)."""
    resolved = {}
    for key, value in properties.items():
        if isinstance(value, str) and value.startswith("@file:"):
            value = (FLOW_DIR / value[len("@file:"):]).read_text()
        elif isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
            value = secrets[value[2:-2]]
        resolved[key] = value
    return resolved


def group_flow(gid):
    return nifi("GET", f"/flow/process-groups/{gid}")["processGroupFlow"]["flow"]


def find_group(root_id, name):
    for g in group_flow(root_id)["processGroups"]:
        if g["component"]["name"] == name:
            return g["id"]
    return None


def wait_stopped(pid, timeout_s=120):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        proc = nifi("GET", f"/processors/{pid}")
        if proc["component"]["state"] == "STOPPED" and proc["status"]["aggregateSnapshot"]["activeThreadCount"] == 0:
            return
        time.sleep(1)
    sys.exit(f"ERROR: processor {pid} did not stop in {timeout_s}s")


def set_run_status(pid, state):
    proc = nifi("GET", f"/processors/{pid}")
    nifi("PUT", f"/processors/{pid}/run-status", {"revision": proc["revision"], "state": state})


def drift(spec, live, secrets):
    """Differences between the spec and a live processor (sensitive values are not compared)."""
    diffs = []
    wanted = resolve(spec["properties"], secrets)
    props = live["component"]["config"]["properties"] or {}
    for key, value in wanted.items():
        if key in SENSITIVE:
            continue
        if props.get(key) != value:
            diffs.append(f"property {key!r}" + ("" if key == "Script Body" else f": live={props.get(key)!r} wanted={value!r}"))
    descriptors = live["component"]["config"].get("descriptors") or {}
    for key, value in props.items():
        # NiFi also returns the defaults of the supported properties: only a value that is not the default
        # (or a property the processor does not support, which has no default) counts as an extra.
        if key not in wanted and key not in SENSITIVE and value is not None \
                and value != (descriptors.get(key) or {}).get("defaultValue"):
            diffs.append(f"property {key!r} is set live ({value!r}) but not in flow.json: it will be removed")
    live_term = sorted(r["name"] for r in live["component"]["relationships"] if r.get("autoTerminate"))
    if live_term != sorted(spec["autoTerminate"]):
        diffs.append(f"auto-terminated relationships: live={live_term} wanted={sorted(spec['autoTerminate'])}")
    return diffs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="only report the differences (the default)")
    ap.add_argument("--apply", action="store_true", help="make the changes")
    args = ap.parse_args()
    if args.check and args.apply:
        sys.exit("ERROR: use either --check or --apply")
    spec = json.loads((FLOW_DIR / "flow.json").read_text())
    secrets = minio_credentials()
    root_id = nifi("GET", "/flow/process-groups/root")["processGroupFlow"]["id"]
    name = spec["processGroup"]

    gid = find_group(root_id, name)
    changes = 0
    if gid is None:
        print(f"+ process group {name!r} (missing)")
        changes += 1
        if not args.apply:
            print("\nNothing else to compare: the group does not exist yet. Run with --apply to create it.")
            return 1
        gid = nifi("POST", f"/process-groups/{root_id}/process-groups", {
            "revision": {"version": 0},
            "component": {"name": name, "position": spec["position"]}})["id"]
    live = {p["component"]["name"]: p for p in group_flow(gid)["processors"]}

    ids = {}
    to_start = []
    for p in spec["processors"]:
        if p["name"] not in live:
            print(f"+ processor {p['name']!r} (missing)")
            changes += 1
            if args.apply:
                created = nifi("POST", f"/process-groups/{gid}/processors", {
                    "revision": {"version": 0},
                    "component": {
                        "type": p["type"], "name": p["name"], "position": p["position"],
                        "bundle": {"group": BUNDLE_GROUP, "artifact": p["bundle"], "version": BUNDLE_VERSION},
                        "config": {"properties": resolve(p["properties"], secrets),
                                   "autoTerminatedRelationships": p["autoTerminate"]}}})
                ids[p["name"]] = created["id"]
                to_start.append(created["id"])
            continue
        proc = live[p["name"]]
        ids[p["name"]] = proc["id"]
        diffs = drift(p, proc, secrets)
        if diffs:
            changes += 1
            print(f"~ processor {p['name']!r} drifted: " + "; ".join(diffs))
            if args.apply:
                set_run_status(proc["id"], "STOPPED")
                wait_stopped(proc["id"])
                fresh = nifi("GET", f"/processors/{proc['id']}")
                nifi("PUT", f"/processors/{proc['id']}", {
                    "revision": fresh["revision"],
                    "component": {"id": proc["id"], "config": {
                        "properties": {**{k: None for k, v in (fresh["component"]["config"]["properties"] or {}).items()
                                          if k not in p["properties"] and k not in SENSITIVE and v is not None
                                          and v != ((fresh["component"]["config"].get("descriptors") or {}).get(k) or {}).get("defaultValue")},
                                       **resolve(p["properties"], secrets)},
                        "autoTerminatedRelationships": p["autoTerminate"]}}})
        if proc["component"]["state"] != "RUNNING" or diffs:
            to_start.append(proc["id"])

    existing = {(c["component"]["source"]["id"], c["component"]["destination"]["id"], r)
                for c in group_flow(gid)["connections"] for r in c["component"]["selectedRelationships"]}
    for c in spec["connections"]:
        src, dst = ids.get(c["from"]), ids.get(c["to"])
        if src and dst and (src, dst, c["relationship"]) in existing:
            continue
        print(f"+ connection {c['from']!r} --{c['relationship']}--> {c['to']!r}")
        changes += 1
        if args.apply:
            nifi("POST", f"/process-groups/{gid}/connections", {
                "revision": {"version": 0},
                "component": {
                    "name": "", "selectedRelationships": [c["relationship"]],
                    "source": {"id": src, "groupId": gid, "type": "PROCESSOR"},
                    "destination": {"id": dst, "groupId": gid, "type": "PROCESSOR"},
                    "backPressureObjectThreshold": 10000, "backPressureDataSizeThreshold": "1 GB",
                    "flowFileExpiration": "0 sec"}})

    if not args.apply:
        print(f"\n{'OK: the live flow matches flow.json' if changes == 0 else str(changes) + ' change(s) pending: run with --apply'}")
        return 0 if changes == 0 else 1

    invalid = []
    for pid in to_start:
        proc = nifi("GET", f"/processors/{pid}")
        errors = proc["component"].get("validationErrors") or []
        if errors:
            invalid.append((proc["component"]["name"], errors))
    for pname, errors in invalid:
        print(f"! {pname!r} is invalid and was not started: {errors}")
    for pid in to_start:
        if not any(pid == ids.get(n) for n, _ in invalid):
            set_run_status(pid, "RUNNING")
    print(f"\nApplied {changes} change(s); {len(to_start) - len(invalid)} processor(s) running.")
    return 1 if invalid else 0


if __name__ == "__main__":
    sys.exit(main())
