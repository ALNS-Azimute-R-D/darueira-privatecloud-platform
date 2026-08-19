#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Continuous Delivery & GitOps Engine
Declarative ArgoCD GitOps Engine, ApplicationSets & OIDC Bootstrapper
==============================================================================
"""

import sys
import os
import json
import time
import base64
import subprocess
import urllib.request
import urllib.error

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
GITOPS_DIR = os.path.join(PROJECT_ROOT, "platform", "gitops", "argocd-apps")
BASE_MGMT_DIR = os.path.join(PROJECT_ROOT, "platform", "kustomize", "base", "corpshared-mgmt")

FORGEJO_HOST = os.environ.get("FORGEJO_HOST", "forgejo-git.drr-corpshared-plat.svc.cluster.local:3000")
FORGEJO_ADMIN_USER = "drradmin"
FORGEJO_ADMIN_PASS = os.environ.get("FORGEJO_ADMIN_PASSWORD", "darueira-admin123")


def run_cmd(cmd, check=True):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and res.returncode != 0:
        print(f"    [!] Command failed: {cmd}\n    Stderr: {res.stderr.strip()}")
        raise RuntimeError(f"Command exited with code {res.returncode}: {res.stderr.strip()}")
    return res


def apply_argocd_server_infrastructure():
    print("--> Applying ArgoCD Server RBAC, Deployments, Secrets & ConfigMaps...")
    run_cmd(f"microk8s kubectl apply -f {os.path.join(BASE_MGMT_DIR, 'argocd-server.yaml')}")
    print("    [✓] ArgoCD base infrastructure manifests applied successfully")


def seed_gitops_manifests_in_forgejo():
    print("--> Ensuring Baseline GitOps Kustomize Manifests in Forgejo platform-core Repository...")
    auth = base64.b64encode(f"{FORGEJO_ADMIN_USER}:{FORGEJO_ADMIN_PASS}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}

    paths = [
        ("platform/kustomize/base/tnt-tenant-base", "tenant-workload"),
        ("platform/kustomize/base/corpshared-secr-internal", "corpshared-secr-internal"),
        ("platform/kustomize/base/corpshared-plat", "corpshared-plat"),
        ("platform/kustomize/base/corpshared-obs", "corpshared-obs"),
        ("platform/kustomize/base/corpshared-mgmt", "corpshared-mgmt")
    ]

    for p, tier in paths:
        kust_content = "apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\nresources:\n  - profile.yaml\n"
        prof_content = f"apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: tier-profile\ndata:\n  tier: \"{tier}\"\n  platform: \"Darueira Private Cloud\"\n"

        for fname, content in [("kustomization.yaml", kust_content), ("profile.yaml", prof_content)]:
            filepath = f"{p}/{fname}"
            payload = {
                "content": base64.b64encode(content.encode()).decode(),
                "message": f"feat(gitops): initialize {filepath}",
                "branch": "main"
            }
            req = urllib.request.Request(
                f"http://{FORGEJO_HOST}/api/v1/repos/darueira-corp/platform-core/contents/{filepath}",
                data=json.dumps(payload).encode(),
                headers=headers,
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    print(f"    [✓] Initialized GitOps manifest: {filepath}")
            except urllib.error.HTTPError as e:
                if e.code in (409, 422):
                    pass
                else:
                    print(f"    [!] Note on {filepath}: HTTP {e.code}")


def apply_argocd_apps_and_appset():
    print("--> Applying Declarative AppProjects, Root Applications, and ApplicationSet...")
    run_cmd(f"microk8s kubectl apply -f {GITOPS_DIR}/")
    print("    [✓] AppProjects, Applications, and ApplicationSet applied successfully")


def wait_for_argocd_reconciliation():
    print("--> Waiting for ArgoCD Controllers Rollout and Application Synchronization...")
    run_cmd("microk8s kubectl rollout status deployment/argocd-server -n drr-corpshared-mgmt --timeout=60s")
    run_cmd("microk8s kubectl rollout status deployment/argocd-application-controller -n drr-corpshared-mgmt --timeout=60s")
    run_cmd("microk8s kubectl rollout status deployment/argocd-applicationset-controller -n drr-corpshared-mgmt --timeout=60s")
    print("    [✓] ArgoCD Core Controllers are healthy and active")


def main():
    print("==================================================================")
    print("  Phase 11: Bootstrapping ArgoCD GitOps Engine & ApplicationSets  ")
    print("==================================================================")

    apply_argocd_server_infrastructure()
    seed_gitops_manifests_in_forgejo()
    apply_argocd_apps_and_appset()
    wait_for_argocd_reconciliation()

    print("\n[✓] ArgoCD GitOps Engine & ApplicationSets bootstrapping completed successfully!")


if __name__ == "__main__":
    main()
