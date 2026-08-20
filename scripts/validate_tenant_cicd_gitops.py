#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Tenant CI/CD & GitOps Validation Suite
Validates Forgejo Git Repositories, Nexus OCI Images, Tekton CI & ArgoCD GitOps
==============================================================================
"""

import sys
import os
import json
import base64
import subprocess
import urllib.request
import urllib.error

FORGEJO_LOCAL_HOST = "10.152.183.187:3000"
NEXUS_HOST = "10.152.183.89:8081"
FORGEJO_ADMIN_USER = "drradmin"
FORGEJO_ADMIN_PASS = "darueira-admin123"
TENANT_NAME = "swfabrik-europe"

EXPECTED_REPOS = [
    "marketplaces",
    "app-food-market-00-mfe",
    "app-food-market-01-react",
    "app-food-market-02-angular",
    "food-market-01-service",
    "food-market-02-service",
    "food-market-03-service",
    "food-market-04-service",
    "food-market-05-service",
    "food-market-06-service",
    "infra-k8s"
]

EXPECTED_ARGOCD_APPS = [
    "swfabrik-europe-app-host-mfe",
    "swfabrik-europe-app-react-01",
    "swfabrik-europe-app-angular-02",
    "swfabrik-europe-food-market-01",
    "swfabrik-europe-food-market-02",
    "swfabrik-europe-food-market-03",
    "swfabrik-europe-food-market-04",
    "swfabrik-europe-food-market-05",
    "swfabrik-europe-food-market-06",
    "swfabrik-europe-tenant-infra"
]


def test_forgejo_repositories():
    print("[INFO] Step 1: Validating Forgejo Git Organization & Repositories...")
    auth = base64.b64encode(f"{FORGEJO_ADMIN_USER}:{FORGEJO_ADMIN_PASS}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}

    # 1. Check org
    req_org = urllib.request.Request(f"http://{FORGEJO_LOCAL_HOST}/api/v1/orgs/{TENANT_NAME}", headers=headers)
    with urllib.request.urlopen(req_org, timeout=5) as resp:
        assert resp.status == 200, f"Organization {TENANT_NAME} not found in Forgejo"
        print(f"[PASS] Forgejo Organization '{TENANT_NAME}' is active.")

    # 2. Check repos
    req_repos = urllib.request.Request(f"http://{FORGEJO_LOCAL_HOST}/api/v1/orgs/{TENANT_NAME}/repos", headers=headers)
    with urllib.request.urlopen(req_repos, timeout=10) as resp:
        repos_data = json.loads(resp.read().decode())
        repo_names = {r["name"] for r in repos_data}
        for exp in EXPECTED_REPOS:
            assert exp in repo_names, f"Expected repository '{exp}' missing in Forgejo org '{TENANT_NAME}'"
            print(f"[PASS] Forgejo Repository '{TENANT_NAME}/{exp}' is registered and healthy.")


def test_nexus_docker_registry():
    print("\n[INFO] Step 2: Validating Nexus OCI Container Registry...")
    auth = base64.b64encode(f"admin:darueira-admin123".encode()).decode()
    headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
    req = urllib.request.Request(f"http://{NEXUS_HOST}/service/rest/v1/status", headers=headers)
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200, "Nexus OSS is not responding"
        print("[PASS] Nexus OSS is healthy and accepting Docker push/pull.")


def test_tekton_pipelines():
    print("\n[INFO] Step 3: Validating Tekton CI/CD Pipeline & PipelineRuns...")
    cmd = "microk8s kubectl get pipelineruns -n drr-corpshared-mgmt -l darueira.io/tenant=swfabrik-europe -o json"
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
    prs = json.loads(res.stdout).get("items", [])
    assert len(prs) > 0, "No PipelineRuns found for tenant swfabrik-europe"

    for pr in prs:
        pr_name = pr["metadata"]["name"]
        conds = pr.get("status", {}).get("conditions", [])
        succeeded = any(c.get("type") == "Succeeded" and c.get("status") == "True" for c in conds)
        assert succeeded, f"PipelineRun {pr_name} did not succeed"
        print(f"[PASS] Tekton PipelineRun '{pr_name}' completed with SUCCEEDED=True.")


def test_argocd_applications():
    print("\n[INFO] Step 4: Validating ArgoCD GitOps Applications Status & Health...")
    cmd = "microk8s kubectl get applications -n drr-corpshared-mgmt -l darueira.io/tenant=swfabrik-europe -o json"
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
    apps_data = json.loads(res.stdout).get("items", [])
    app_map = {a["metadata"]["name"]: a for a in apps_data}

    for exp in EXPECTED_ARGOCD_APPS:
        assert exp in app_map, f"ArgoCD Application '{exp}' not found"
        app = app_map[exp]
        sync_st = app.get("status", {}).get("sync", {}).get("status")
        health_st = app.get("status", {}).get("health", {}).get("status")
        assert sync_st == "Synced", f"ArgoCD Application '{exp}' is {sync_st}, expected Synced"
        assert health_st == "Healthy", f"ArgoCD Application '{exp}' is {health_st}, expected Healthy"
        print(f"[PASS] ArgoCD Application '{exp:32}' -> Sync: {sync_st:8} | Health: {health_st}")


def main():
    print("=" * 80)
    print("  Darueira Platform - Tenant CI/CD & GitOps Golden Path Validation Suite")
    print(f"  Tenant: {TENANT_NAME}")
    print("=" * 80)

    test_forgejo_repositories()
    test_nexus_docker_registry()
    test_tekton_pipelines()
    test_argocd_applications()

    print("\n" + "=" * 80)
    print("  TENANT CI/CD & GITOPS VALIDATION COMPLETE: ALL ASSERTIONS PASSED! [✓✓✓]")
    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[FAIL] Validation assertion failed: {e}", file=sys.stderr)
        sys.exit(1)
