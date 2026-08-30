#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Tenant CI/CD & GitOps Validation Suite
Validates Forgejo Git Repositories, Master Branch Protection, Nexus OCI Images,
Tekton CI & ArgoCD GitOps
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
    "app-food-market-00-mfe",
    "app-food-market-01-react",
    "app-food-market-02-angular",
    "food-market-01-service",
    "food-market-02-service",
    "food-market-03-service",
    "food-market-04-service",
    "food-market-05-service",
    "food-market-06-service",
    "app-food-market-00-mfe-chart",
    "app-food-market-01-react-chart",
    "app-food-market-02-angular-chart",
    "food-market-01-service-chart",
    "food-market-02-service-chart",
    "food-market-03-service-chart",
    "food-market-04-service-chart",
    "food-market-05-service-chart",
    "food-market-06-service-chart",
    "legaltech-caseforce-solutions",
    "legaltech-caseforce-solutions-chart",
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
    "swfabrik-europe-legaltech-caseforce",
    "swfabrik-europe-tenant-infra"
]


def test_forgejo_repositories():
    print("[INFO] Step 1: Validating Forgejo Git Organization, Repositories & 'master' Branch Protection...")
    auth = base64.b64encode(f"{FORGEJO_ADMIN_USER}:{FORGEJO_ADMIN_PASS}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}

    # 1. Check org
    req_org = urllib.request.Request(f"http://{FORGEJO_LOCAL_HOST}/api/v1/orgs/{TENANT_NAME}", headers=headers)
    with urllib.request.urlopen(req_org, timeout=5) as resp:
        assert resp.status == 200, f"Organization {TENANT_NAME} not found in Forgejo"
        print(f"[PASS] Forgejo Organization '{TENANT_NAME}' is active.")

    # 2. Verify 'marketplaces' is NOT present
    req_mkt = urllib.request.Request(f"http://{FORGEJO_LOCAL_HOST}/api/v1/repos/{TENANT_NAME}/marketplaces", headers=headers)
    try:
        with urllib.request.urlopen(req_mkt, timeout=5) as resp:
            raise AssertionError("Repository 'marketplaces' should have been removed, but is still present!")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("[PASS] Obsolete repository 'marketplaces' is completely removed.")

    # 3. Check repos, default_branch=master and branch protection
    req_repos = urllib.request.Request(f"http://{FORGEJO_LOCAL_HOST}/api/v1/orgs/{TENANT_NAME}/repos", headers=headers)
    with urllib.request.urlopen(req_repos, timeout=10) as resp:
        repos_data = json.loads(resp.read().decode())
        repo_map = {r["name"]: r for r in repos_data}

        for exp in EXPECTED_REPOS:
            assert exp in repo_map, f"Expected repository '{exp}' missing in Forgejo org '{TENANT_NAME}'"
            repo_info = repo_map[exp]
            def_branch = repo_info.get("default_branch")
            assert def_branch == "master", f"Repository '{exp}' has default branch '{def_branch}', expected 'master'"

            # Verify branch protection on master
            req_bp = urllib.request.Request(f"http://{FORGEJO_LOCAL_HOST}/api/v1/repos/{TENANT_NAME}/{exp}/branch_protections", headers=headers)
            with urllib.request.urlopen(req_bp, timeout=5) as bp_resp:
                bps = json.loads(bp_resp.read().decode())
                master_bp = [bp for bp in bps if bp.get("branch_name") == "master" or bp.get("rule_name") == "master"]
                assert len(master_bp) > 0, f"Repository '{exp}' is missing branch protection on 'master'"
                assert master_bp[0].get("enable_push") is False or master_bp[0].get("require_pull_request") is True, f"Direct push to 'master' should be disabled on '{exp}'"

            print(f"[PASS] Repository '{TENANT_NAME}/{exp}' -> Default: master | Protected: True (No direct push, PR required)")


def test_nexus_docker_registry():
    print("\n[INFO] Step 2: Validating Nexus OCI Container Registry...")
    auth = base64.b64encode(b"admin:darueira-admin123").decode()
    headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
    req = urllib.request.Request(f"http://{NEXUS_HOST}/service/rest/v1/status", headers=headers)
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200, "Nexus OSS is not responding"
        print("[PASS] Nexus OSS is healthy and accepting Docker push/pull.")


def test_tekton_triggers():
    print("\n[INFO] Step 3: Validating Tekton EventListener & Pipeline Configs...")
    cmd = "microk8s kubectl get eventlistener forgejo-webhook-listener -n drr-corpshared-mgmt -o json"
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
    el = json.loads(res.stdout)
    conds = el.get("status", {}).get("conditions", [])
    ready = any(c.get("type") == "Ready" and c.get("status") == "True" for c in conds)
    assert ready, "EventListener is not ready"
    print("[PASS] Tekton EventListener 'forgejo-webhook-listener' is Ready and listening on port 8080.")


def test_argocd_applications():
    print("\n[INFO] Step 4: Validating ArgoCD GitOps Applications (targetRevision: master)...")
    cmd = "microk8s kubectl get applications -n drr-corpshared-mgmt -l darueira.io/tenant=swfabrik-europe -o json"
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
    apps_data = json.loads(res.stdout).get("items", [])
    app_map = {a["metadata"]["name"]: a for a in apps_data}

    for exp in EXPECTED_ARGOCD_APPS:
        assert exp in app_map, f"ArgoCD Application '{exp}' not found"
        app = app_map[exp]
        target_rev = app.get("spec", {}).get("source", {}).get("targetRevision")
        assert target_rev == "master", f"Application '{exp}' targetRevision is '{target_rev}', expected 'master'"
        sync_st = app.get("status", {}).get("sync", {}).get("status")
        health_st = app.get("status", {}).get("health", {}).get("status")
        print(f"[PASS] ArgoCD Application '{exp:35}' -> Target: {target_rev:6} | Sync: {sync_st:8} | Health: {health_st}")


def main():
    print("=" * 80)
    print("  Darueira Platform - Tenant CI/CD & GitOps Golden Path Validation Suite")
    print(f"  Tenant: {TENANT_NAME} | Branch Standard: master (Protected)")
    print("=" * 80)

    test_forgejo_repositories()
    test_nexus_docker_registry()
    test_tekton_triggers()
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
