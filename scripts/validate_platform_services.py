#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Core Platform Microservices & Operator
Validation Suite for drr-tenant-svc, drr-iam-authz-svc, drr-env-orchestrator-svc,
darueira-operator Reconciler and drr-ctlr-cli Developer CLI
==============================================================================
"""

import sys
import os
import json
import time
import subprocess
import urllib.request
import urllib.error

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

AUTHZ_SVC_HOST = os.environ.get("AUTHZ_SVC_HOST", "drr-iam-authz-svc.drr-corpshared-plat.svc.cluster.local:8080")
TENANT_SVC_HOST = os.environ.get("TENANT_SVC_HOST", "drr-tenant-svc.drr-corpshared-plat.svc.cluster.local:8081")
ENV_ORCH_SVC_HOST = os.environ.get("ENV_ORCH_SVC_HOST", "drr-env-orchestrator-svc.drr-corpshared-mgmt.svc.cluster.local:8082")


def run_cmd(cmd, check=True):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT)
    if check and res.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}\nStderr: {res.stderr.strip()}")
    return res


def test_microservices_and_operator_pods():
    # 1. Platform namespace
    cmd1 = "microk8s kubectl get pods -n drr-corpshared-plat -o json"
    res1 = run_cmd(cmd1)
    pods1 = json.loads(res1.stdout).get("items", [])
    running1 = {p["metadata"]["labels"].get("app.kubernetes.io/name") for p in pods1 if p.get("status", {}).get("phase") == "Running"}
    assert "drr-iam-authz-svc" in running1 or "iam-authz-svc" in running1, "drr-iam-authz-svc pod is not Running"
    assert "drr-tenant-svc" in running1 or "tenant-svc" in running1, "drr-tenant-svc pod is not Running"

    # 2. Management namespace
    cmd2 = "microk8s kubectl get pods -n drr-corpshared-mgmt -o json"
    res2 = run_cmd(cmd2)
    pods2 = json.loads(res2.stdout).get("items", [])
    running2 = {p["metadata"]["labels"].get("app.kubernetes.io/name") for p in pods2 if p.get("status", {}).get("phase") == "Running"}
    assert "drr-env-orchestrator-svc" in running2 or "env-orchestrator-svc" in running2, "drr-env-orchestrator-svc pod is not Running"
    assert "darueira-operator" in running2, "darueira-operator pod is not Running"

    return len(running1) + len(running2)


def test_iam_authz_service():
    # 1. Health check
    req = urllib.request.Request(f"http://{AUTHZ_SVC_HOST}/healthz")
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200, f"Expected HTTP 200, got {resp.status}"
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("status") == "UP"

    # 2. OpenFGA Check Permission (Alice Developer in ACME)
    payload_allowed = json.dumps({
        "user": "user:alice.developer",
        "relation": "can_read",
        "object": "environment:acme-storefront-prod"
    }).encode("utf-8")
    req_check1 = urllib.request.Request(
        f"http://{AUTHZ_SVC_HOST}/api/v1/authz/check",
        data=payload_allowed,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req_check1, timeout=10) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("allowed") is True, f"Expected Alice allowed to read ACME environment, got: {data}"

    # 3. OpenFGA Check Zero Trust Isolation (Carol in Globex blocked from ACME environment)
    payload_denied = json.dumps({
        "user": "user:carol.contractor",
        "relation": "can_read",
        "object": "environment:acme-storefront-prod"
    }).encode("utf-8")
    req_check2 = urllib.request.Request(
        f"http://{AUTHZ_SVC_HOST}/api/v1/authz/check",
        data=payload_denied,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req_check2, timeout=10) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("allowed") is False, f"Expected Carol denied from ACME environment, got: {data}"

    return True


def test_tenant_management_service():
    # 1. Health check
    req = urllib.request.Request(f"http://{TENANT_SVC_HOST}/healthz")
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200, f"Expected HTTP 200, got {resp.status}"
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("status") in ("healthy", "UP")

    # 2. List Tenants
    req_list = urllib.request.Request(f"http://{TENANT_SVC_HOST}/api/v1/tenants")
    with urllib.request.urlopen(req_list, timeout=10) as resp:
        assert resp.status == 200
        tenants = json.loads(resp.read().decode("utf-8"))
        assert len(tenants) >= 1, "Expected at least default seeded tenant 'darueira-corp'"
        return len(tenants)


def test_env_orchestrator_service():
    # 1. Health check
    req = urllib.request.Request(f"http://{ENV_ORCH_SVC_HOST}/healthz")
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200, f"Expected HTTP 200, got {resp.status}"
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("status") in ("healthy", "UP")

    # 2. List Environments
    req_list = urllib.request.Request(f"http://{ENV_ORCH_SVC_HOST}/api/v1/environments")
    with urllib.request.urlopen(req_list, timeout=10) as resp:
        assert resp.status == 200
        envs = json.loads(resp.read().decode("utf-8"))
        assert len(envs) >= 1, "Expected at least default seeded environment"
        return len(envs)


def test_darueira_operator_reconciliation():
    # 1. Create CRDs for a temporary test tenant/project/environment
    crd_yaml = """
apiVersion: darueira.io/v1alpha1
kind: Tenant
metadata:
  name: val-tenant
spec:
  displayName: "Validation Tenant Corp"
  description: "Temporary validation tenant for test suite"
  adminEmail: "admin@val.local"
---
apiVersion: darueira.io/v1alpha1
kind: Project
metadata:
  name: val-proj
spec:
  tenantRef: val-tenant
  description: "Validation Project"
  ownerEmail: "owner@val.local"
  enabled: true
---
apiVersion: darueira.io/v1alpha1
kind: Environment
metadata:
  name: val-proj-dev
spec:
  tenantRef: val-tenant
  projectRef: val-proj
  type: dev
"""
    run_cmd(f"echo '{crd_yaml}' | microk8s kubectl apply -f -")

    # 2. Wait for Operator to reconcile the environment namespace
    target_ns = "drr-tnt-val-tenant-val-proj-dev"
    reconciled = False
    for _ in range(15):
        time.sleep(1)
        res = run_cmd(f"microk8s kubectl get ns {target_ns} -o json", check=False)
        if res.returncode == 0:
            reconciled = True
            break
    assert reconciled, f"darueira-operator failed to create namespace {target_ns}"

    # 3. Assert PSS labels on created namespace
    res_ns = run_cmd(f"microk8s kubectl get ns {target_ns} -o json")
    ns_obj = json.loads(res_ns.stdout)
    labels = ns_obj.get("metadata", {}).get("labels", {})
    assert labels.get("pod-security.kubernetes.io/enforce") == "restricted", "PSS restricted label missing"

    # 4. Assert Envoy & OPA sidecar ConfigMaps exist
    res_cm = run_cmd(f"microk8s kubectl get cm -n {target_ns} -o json")
    cms = [c["metadata"]["name"] for c in json.loads(res_cm.stdout).get("items", [])]
    assert "envoy-sidecar-config" in cms, "envoy-sidecar-config ConfigMap missing in reconciled namespace"
    assert "opa-policy-config" in cms, "opa-policy-config ConfigMap missing in reconciled namespace"

    # 5. Assert CRD status is Active and Ready
    res_env = run_cmd("microk8s kubectl get environment val-proj-dev -o json")
    env_obj = json.loads(res_env.stdout)
    status = env_obj.get("status", {})
    assert status.get("phase") == "Active", f"Environment phase not Active: {status}"
    assert status.get("ready") is True, f"Environment ready flag not True: {status}"

    # 6. Cleanup test resources
    run_cmd("microk8s kubectl delete environment/val-proj-dev project/val-proj tenant/val-tenant --wait=false", check=False)
    run_cmd(f"microk8s kubectl delete ns {target_ns} --wait=false", check=False)

    return target_ns


def test_cli_execution():
    cli_path = os.path.join(PROJECT_ROOT, "bin", "drr-ctlr-cli")
    assert os.path.exists(cli_path), f"CLI binary not found at {cli_path}"

    res_ver = run_cmd(f"{cli_path} version")
    assert "drr-ctlr-cli version" in res_ver.stdout, "CLI version command failed"

    res_help = run_cmd(f"{cli_path} --help")
    assert "drr-ctlr-cli is the operational command-line tool" in res_help.stdout, "CLI help command failed"

    return "drr-ctlr-cli v0.2.0 (Operational)"


def main():
    print("==================================================================")
    print("  Phase 13: Core Platform Microservices & Operator Validation     ")
    print("==================================================================")

    # 1. Pod Health
    print("\n[1/6] Validating Core Microservices & Operator Pods Health...")
    total_pods = test_microservices_and_operator_pods()
    print(f"      [✓] All Core Microservices & darueira-operator Pods active ({total_pods} services running)")

    # 2. IAM & Authz Gateway
    print("\n[2/6] Validating IAM & Authz Gateway API (:8080) & OpenFGA ReBAC...")
    allowed = test_iam_authz_service()
    print(f"      [✓] drr-iam-authz-svc active -> OpenFGA ReBAC Permission Check Verified (Allowed: {allowed})")

    # 3. Tenant Management Service
    print("\n[3/6] Validating Tenant & Project Management API (:8081)...")
    tenants = test_tenant_management_service()
    print(f"      [✓] drr-tenant-svc active -> {tenants} tenant(s) available via REST API")

    # 4. Environment Orchestrator Service
    print("\n[4/6] Validating Environment Orchestration API (:8082)...")
    envs = test_env_orchestrator_service()
    print(f"      [✓] drr-env-orchestrator-svc active -> {envs} environment(s) available via REST API")

    # 5. Kubernetes Operator Reconciler
    print("\n[5/6] Validating darueira-operator CRDs & Zero Trust Auto-Provisioning...")
    target_ns = test_darueira_operator_reconciliation()
    print(f"      [✓] darueira-operator successfully reconciled CRDs, PSS restricted namespace & sidecar configs ({target_ns})")

    # 6. Developer CLI
    print("\n[6/6] Validating Developer & Platform Engineer CLI (drr-ctlr-cli)...")
    cli_status = test_cli_execution()
    print(f"      [✓] {cli_status} compiled and executing commands successfully")

    print("\n==================================================================")
    print("  [✓✓✓] ALL PHASE 13 PLATFORM SERVICES & OPERATOR TESTS PASSED!   ")
    print("==================================================================")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[✗] Validation failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
