#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Enterprise Shared Services
OpenFGA store + authorization model provisioning (ADR-0021)
==============================================================================
The authorization model comes from authz/schema.fga, the source of truth (SDD): it is converted with the official
`openfga/cli` image (`fga model transform`), so no model is duplicated in this script.

What it does (idempotent):
  1. converts authz/schema.fga to the JSON model;
  2. creates the store `darueira-rebac-store` if it does not exist;
  3. writes a new authorization model only if it differs from the latest one;
  4. records the ids in the ConfigMap `openfga-ids` (drr-corpshared-plat) and restarts drr-iam-authz-svc when they changed.

It writes NO relationship tuples: tuples are written by the platform (drr-tenant-svc writes `user:<id> admin tenant:<id>` when a
tenant is created). Granting permissions to existing tenants is a separate decision of the platform owner.

Requirements: kubectl access to the cluster and docker (for the fga CLI image). OpenFGA is reached through a temporary
`kubectl port-forward`.

Usage: python3 scripts/bootstrap_openfga_rebac.py [--no-restart]
  --no-restart  record the ids but do not restart drr-iam-authz-svc (the operator restarts it).
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

NAMESPACE = "drr-corpshared-plat"
STORE_NAME = "darueira-rebac-store"
IDS_CONFIGMAP = "openfga-ids"
CONSUMER_DEPLOYMENT = "drr-iam-authz-svc"
FGA_CLI_IMAGE = os.environ.get("FGA_CLI_IMAGE", "openfga/cli:latest")
LOCAL_PORT = int(os.environ.get("OPENFGA_LOCAL_PORT", "18080"))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUTHZ_DIR = os.path.join(ROOT, "authz")


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, check=True, **kw).stdout


def api(method, path, body=None):
    req = urllib.request.Request(
        f"http://127.0.0.1:{LOCAL_PORT}{path}", method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"OpenFGA {method} {path} -> {e.code}: {e.read().decode()}") from e


def transform_model():
    out = run(["docker", "run", "--rm", "-v", f"{AUTHZ_DIR}:/authz:ro", FGA_CLI_IMAGE,
               "model", "transform", "--file", "/authz/schema.fga"])
    model = json.loads(out)
    if not model.get("type_definitions"):
        sys.exit("schema.fga produced an empty model")
    return model


def canonical(model):
    """Comparable form: the server may add/omit empty fields, so keep only what defines the model."""
    return json.dumps({"schema_version": model.get("schema_version"),
                       "type_definitions": sorted(model.get("type_definitions", []), key=lambda t: t["type"])},
                      sort_keys=True)


def get_or_create_store():
    for s in api("GET", "/stores").get("stores", []):
        if s.get("name") == STORE_NAME:
            print(f"    [=] Store reused: {s['id']}")
            return s["id"], False
    s = api("POST", "/stores", {"name": STORE_NAME})
    print(f"    [+] Store created: {s['id']}")
    return s["id"], True


def ensure_model(store_id, model):
    latest = api("GET", f"/stores/{store_id}/authorization-models?page_size=1").get("authorization_models", [])
    if latest and canonical(latest[0]) == canonical(model):
        print(f"    [=] Model unchanged: {latest[0]['id']}")
        return latest[0]["id"]
    created = api("POST", f"/stores/{store_id}/authorization-models", model)
    print(f"    [+] Model written: {created['authorization_model_id']}")
    return created["authorization_model_id"]


def record_ids(store_id, model_id):
    """ConfigMap with the ids; restarts the consumer when they changed."""
    current = {}
    try:
        current = json.loads(run(["kubectl", "-n", NAMESPACE, "get", "cm", IDS_CONFIGMAP, "-o", "jsonpath={.data}"]) or "{}")
    except subprocess.CalledProcessError:
        pass
    desired = {"store-id": store_id, "model-id": model_id}
    manifest = run(["kubectl", "-n", NAMESPACE, "create", "configmap", IDS_CONFIGMAP,
                    f"--from-literal=store-id={store_id}", f"--from-literal=model-id={model_id}",
                    "--dry-run=client", "-o", "yaml"])
    labelled = run(["kubectl", "-n", NAMESPACE, "label", "--local", "-f", "-", "app.kubernetes.io/name=openfga",
                    "darueira.io/tier=enterprise-shared", "-o", "yaml"], input=manifest)
    subprocess.run(["kubectl", "apply", "-f", "-"], input=labelled, capture_output=True, text=True, check=True)
    if current == desired:
        print(f"    [=] ConfigMap {IDS_CONFIGMAP} unchanged")
        return False
    print(f"    [+] ConfigMap {IDS_CONFIGMAP} updated")
    return True


def main():
    print("==================================================================")
    print("  OpenFGA store + authorization model (from authz/schema.fga)     ")
    print("==================================================================")
    model = transform_model()
    print(f"    [=] schema.fga: {len(model['type_definitions'])} types")
    pf = subprocess.Popen(["kubectl", "-n", NAMESPACE, "port-forward", "svc/openfga", f"{LOCAL_PORT}:8080"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(30):
            try:
                api("GET", "/stores")
                break
            except Exception:
                time.sleep(1)
        else:
            sys.exit("OpenFGA is not reachable through port-forward")
        store_id, _ = get_or_create_store()
        model_id = ensure_model(store_id, model)
    finally:
        pf.terminate()
    changed = record_ids(store_id, model_id)
    if changed and "--no-restart" not in sys.argv:
        run(["kubectl", "-n", NAMESPACE, "rollout", "restart", f"deploy/{CONSUMER_DEPLOYMENT}"])
        print(f"    [+] {CONSUMER_DEPLOYMENT} restarted to pick up the new ids")
    elif changed:
        print(f"    [!] ids changed: restart {CONSUMER_DEPLOYMENT} to pick them up")
    print("\n[✓] OpenFGA store and model are in place (no tuples written, by design).")


if __name__ == "__main__":
    main()
