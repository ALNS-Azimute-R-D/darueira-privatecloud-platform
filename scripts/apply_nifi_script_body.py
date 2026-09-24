#!/usr/bin/env python3
"""
Apply a version-controlled Groovy file as the "Script Body" of a live NiFi
ExecuteScript processor, so the scripts under platform/nifi/ are the source of
truth instead of edits made in the NiFi UI.

NiFi only accepts configuration changes on a stopped processor, so this does:
stop -> wait for active threads to drain -> update Script Body -> start again.
It is a no-op when the live body already matches the file.

Auth: mTLS with the node keystore from inside the apache-nifi pod (its cert DN
is a NiFi user with flow permissions), so no OIDC token is needed.

Usage:
  scripts/apply_nifi_script_body.py "8. Ingest Backend & Summarize" \
      platform/nifi/bookanything-geolocation-ingestion/08-ingest-backend-and-summarize.groovy
  scripts/apply_nifi_script_body.py --check "<processor name>" <file>   # diff only
"""
import json
import subprocess
import sys
import time
import urllib.parse

NAMESPACE = "drr-corpshared-plat"
DEPLOYMENT = "deploy/apache-nifi"
API = "https://localhost:8443/nifi-api"
CERT = "/opt/nifi/certs/keystore.p12:darueira-keystore-pass"


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


def find_processor(name):
    res = nifi("GET", "/flow/search-results?q=" + urllib.parse.quote(name))
    matches = [p for p in res["searchResultsDTO"]["processorResults"] if p["name"] == name]
    if len(matches) != 1:
        sys.exit(f"ERROR: expected exactly one processor named {name!r}, found {len(matches)}")
    return matches[0]["id"]


def set_run_status(pid, state):
    proc = nifi("GET", f"/processors/{pid}")
    nifi("PUT", f"/processors/{pid}/run-status", {"revision": proc["revision"], "state": state})


def wait_stopped(pid, timeout_s=300):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status = nifi("GET", f"/flow/processors/{pid}/status")["processorStatus"]
        snap = status["aggregateSnapshot"]
        if status["runStatus"] == "Stopped" and snap.get("activeThreadCount", 0) == 0:
            return
        time.sleep(2)
    sys.exit("ERROR: processor did not stop within the timeout; it is left STOPPED, check it in the NiFi UI")


def main():
    args = sys.argv[1:]
    check_only = args and args[0] == "--check"
    if check_only:
        args = args[1:]
    if len(args) != 2:
        sys.exit(__doc__)
    name, path = args
    with open(path, encoding="utf-8") as f:
        new_body = f.read()

    pid = find_processor(name)
    proc = nifi("GET", f"/processors/{pid}")
    live_body = proc["component"]["config"]["properties"].get("Script Body") or ""
    if live_body == new_body:
        print(f"==> {name}: live Script Body already matches {path}")
        return
    if check_only:
        print(f"==> DRIFT {name}: live Script Body differs from {path} ({len(live_body)} vs {len(new_body)} chars)")
        sys.exit(1)

    was_running = proc["component"]["state"] == "RUNNING"
    print(f"==> {name} ({pid}): state={proc['component']['state']}")
    if was_running:
        set_run_status(pid, "STOPPED")
        wait_stopped(pid)
        print("    stopped")

    proc = nifi("GET", f"/processors/{pid}")
    nifi("PUT", f"/processors/{pid}", {
        "revision": proc["revision"],
        "component": {"id": pid, "config": {"properties": {"Script Body": new_body}}},
    })
    print(f"    Script Body updated from {path} ({len(new_body)} chars)")

    if was_running:
        set_run_status(pid, "RUNNING")
        print("    started")

    applied = nifi("GET", f"/processors/{pid}")["component"]
    if applied["config"]["properties"].get("Script Body") != new_body:
        sys.exit("ERROR: live Script Body does not match the file after update")
    errors = applied.get("validationErrors") or []
    if errors:
        sys.exit(f"ERROR: processor is invalid after update: {errors}")
    print(f"==> done: state={applied['state']}, body verified")


if __name__ == "__main__":
    main()
