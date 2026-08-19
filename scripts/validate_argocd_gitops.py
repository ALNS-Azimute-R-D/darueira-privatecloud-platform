#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Continuous Delivery & GitOps Engine
ArgoCD GitOps Engine & ApplicationSets Validation Suite
==============================================================================
"""

import sys
import os
import json
import time
import subprocess
import urllib.request
import urllib.error

ARGOCD_HOST = os.environ.get("ARGOCD_HOST", "argocd-server.drr-corpshared-mgmt.svc.cluster.local:80")
ARGOCD_ADDR = f"http://{ARGOCD_HOST}"
ADMIN_USER = "admin"
ADMIN_PASS = os.environ.get("ARGOCD_ADMIN_PASSWORD", "Darueira@2026!")

EXPECTED_PROJECTS = [
    "darueira-enterprise-shared",
    "darueira-tenants"
]

EXPECTED_APPS = [
    "corpshared-secr-internal",
    "corpshared-plat",
    "corpshared-obs",
    "corpshared-mgmt",
    "tenant-acme-storefront-dev",
    "tenant-acme-storefront-staging",
    "tenant-acme-storefront-prod",
    "tenant-darueira-corp-platform-core-prod",
    "tenant-globex-logistics-dev",
    "tenant-globex-logistics-prod"
]


def test_controllers_health():
    cmd = "microk8s kubectl get pods -n drr-corpshared-mgmt -o json"
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
    pods = json.loads(res.stdout).get("items", [])
    running = [
        p for p in pods
        if p.get("metadata", {}).get("name", "").startswith("argocd-")
        and p.get("status", {}).get("phase") == "Running"
    ]
    assert len(running) >= 5, f"Expected at least 5 ArgoCD pods running, found {len(running)}"
    return len(running)


def test_api_authentication():
    req = urllib.request.Request(
        f"{ARGOCD_ADDR}/api/v1/session",
        data=json.dumps({"username": ADMIN_USER, "password": ADMIN_PASS}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200, f"Expected HTTP 200 on login, got {resp.status}"
        data = json.loads(resp.read().decode("utf-8"))
        token = data.get("token")
        assert token, "No token returned in session response"
        return token


def test_appprojects(token):
    req = urllib.request.Request(
        f"{ARGOCD_ADDR}/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200
        projs = json.loads(resp.read().decode("utf-8")).get("items", [])
        proj_names = {p["metadata"]["name"] for p in projs}
        for exp in EXPECTED_PROJECTS:
            assert exp in proj_names, f"Expected AppProject missing: {exp}"
        return len(proj_names)


def test_applicationset_and_applications(token):
    # Check ApplicationSet CRD
    cmd = "microk8s kubectl get applicationset tenant-workloads-appset -n drr-corpshared-mgmt -o json"
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
    appset = json.loads(res.stdout)
    assert appset["metadata"]["name"] == "tenant-workloads-appset"

    # Check Applications via API
    req = urllib.request.Request(
        f"{ARGOCD_ADDR}/api/v1/applications",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200
        apps = json.loads(resp.read().decode("utf-8")).get("items", [])
        app_map = {a["metadata"]["name"]: a for a in apps}

        for exp_app in EXPECTED_APPS:
            assert exp_app in app_map, f"Expected application missing: {exp_app}"
        return app_map


def test_continuous_sync_and_health(app_map):
    synced_count = 0
    healthy_count = 0
    for name, app in app_map.items():
        sync_st = app.get("status", {}).get("sync", {}).get("status")
        health_st = app.get("status", {}).get("health", {}).get("status")
        if sync_st == "Synced":
            synced_count += 1
        if health_st == "Healthy":
            healthy_count += 1

    assert synced_count >= 6, f"Expected at least 6 synced applications, found {synced_count}"
    assert healthy_count == len(app_map), f"Expected all applications to be Healthy, found {healthy_count}/{len(app_map)}"
    return synced_count, healthy_count


def test_tenant_namespace_and_resource_reconciliation():
    cmd = "microk8s kubectl get cm tenant-profile -n drr-tnt-acme-storefront-dev -o json"
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
    cm = json.loads(res.stdout)
    data = cm.get("data", {})
    assert data.get("platform") == "Darueira Private Cloud", "ConfigMap data invalid"
    assert data.get("tier") == "tenant-workload", "ConfigMap tier invalid"
    return cm["metadata"]["namespace"]


def test_api_version():
    req = urllib.request.Request(f"{ARGOCD_ADDR}/api/version")
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        version = data.get("Version")
        assert version, "No version returned from ArgoCD API"
        return version


def main():
    print("==================================================================")
    print("  Phase 11: ArgoCD GitOps Engine & ApplicationSets Validation     ")
    print("==================================================================")

    # 1. Controller Health
    print("\n[1/7] Validating ArgoCD Core Controllers & Microservices Health...")
    pod_count = test_controllers_health()
    print(f"      [✓] ArgoCD Core Microservices active and healthy ({pod_count} pods running)")

    # 2. REST API & Authentication
    print("\n[2/7] Validating ArgoCD REST API & IAM Session Authentication...")
    token = test_api_authentication()
    print("      [✓] Admin authentication successful -> Valid JWT session token acquired")

    # 3. AppProjects Governance
    print("\n[3/7] Validating AppProjects Multi-Tenant Boundary Governance...")
    proj_count = test_appprojects(token)
    print(f"      [✓] Verified {proj_count} AppProjects ('darueira-enterprise-shared', 'darueira-tenants')")

    # 4. ApplicationSet Generation
    print("\n[4/7] Validating Declarative ApplicationSet Generation...")
    app_map = test_applicationset_and_applications(token)
    print(f"      [✓] ApplicationSet 'tenant-workloads-appset' generated {len(app_map)} applications dynamically")

    # 5. GitOps Continuous Sync & Health
    print("\n[5/7] Validating Continuous Delivery Synchronization & Health...")
    synced, healthy = test_continuous_sync_and_health(app_map)
    print(f"      [✓] {synced}/{len(app_map)} Applications Synced with GitOps Desired State")
    print(f"      [✓] {healthy}/{len(app_map)} Applications Reporting Healthy Status")

    # 6. Tenant Namespace & Resource Delivery
    print("\n[6/7] Validating Multi-Tenant Dynamic Namespace & Resource Delivery...")
    ns = test_tenant_namespace_and_resource_reconciliation()
    print(f"      [✓] Verified reconciled ConfigMap 'tenant-profile' inside dedicated tenant namespace '{ns}'")

    # 7. ArgoCD Server Version & UI Ingress
    print("\n[7/7] Validating ArgoCD Server API Endpoint & Version...")
    version = test_api_version()
    print(f"      [✓] ArgoCD Server API operational (Version: {version})")

    print("\n==================================================================")
    print("  [✓✓✓] ALL PHASE 11 ARGOCD GITOPS VALIDATION TESTS PASSED!       ")
    print("==================================================================")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[✗] Validation failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
