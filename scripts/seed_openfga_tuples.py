#!/usr/bin/env python3
"""
Applies authz/seed-tuples.json to the OpenFGA store through the internal API of drr-iam-authz-svc (the same path drr-tenant-svc
uses), over a temporary `kubectl port-forward`. Idempotent: a tuple that already holds is skipped. Only INSERTs: it never deletes.
After writing it checks every tuple with /check and proves the model derives `member` from `admin`.

Usage: python3 scripts/seed_openfga_tuples.py [--dry-run]
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(os.environ.get("AUTHZ_LOCAL_PORT", "18082"))
BASE = f"http://127.0.0.1:{PORT}/api/v1/authz"


def call(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:200]}


def allowed(t):
    status, body = call("POST", "/check", {"user": t["user"], "relation": t["relation"], "object": t["object"]})
    if status != 200:
        sys.exit(f"check failed for {t}: HTTP {status} {body}")
    return bool(body.get("allowed"))


def main():
    dry = "--dry-run" in sys.argv
    tuples = json.load(open(os.path.join(ROOT, "authz", "seed-tuples.json")))["tuples"]
    pf = subprocess.Popen(["kubectl", "-n", "drr-corpshared-plat", "port-forward", "svc/drr-iam-authz-svc", f"{PORT}:8080"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(30):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/readyz", timeout=2)
                break
            except Exception:
                time.sleep(1)
        for t in tuples:
            label = f"{t['user']} {t['relation']} {t['object']}"
            if allowed(t):
                print(f"[=] already holds: {label}")
            elif dry:
                print(f"[?] would write:   {label}")
            else:
                status, body = call("POST", "/tuples", {"action": "INSERT", "tuple": {k: t[k] for k in ("user", "relation", "object")}})
                if status not in (200, 202):
                    sys.exit(f"could not write {label}: HTTP {status} {body}")
                print(f"[+] written:       {label}")
        if dry:
            return
        for t in tuples:
            assert allowed(t), f"tuple does not hold after the write: {t}"
        # The model derives member from admin; a stranger must stay denied.
        for t in tuples:
            if t["relation"] == "admin":
                derived = {"user": t["user"], "relation": "member", "object": t["object"]}
                stranger = {"user": "user:nobody-in-particular", "relation": "member", "object": t["object"]}
                assert allowed(derived), f"member must follow from admin: {derived}"
                assert not allowed(stranger), f"a stranger must not be a member: {stranger}"
        print(f"[✓] {len(tuples)} tuple(s) verified (direct, derived member, stranger denied)")
    finally:
        pf.terminate()


if __name__ == "__main__":
    main()
