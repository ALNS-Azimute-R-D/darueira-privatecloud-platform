#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Continuous Delivery & GitOps Engine
Declarative ArgoCD GitOps Engine, ApplicationSets & OIDC Bootstrapper
==============================================================================
"""

import sys
import os
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
GITOPS_DIR = os.path.join(PROJECT_ROOT, "platform", "gitops", "argocd-apps")
BASE_MGMT_DIR = os.path.join(PROJECT_ROOT, "platform", "kustomize", "base", "corpshared-mgmt")


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
    apply_argocd_apps_and_appset()
    wait_for_argocd_reconciliation()

    print("\n[✓] ArgoCD GitOps Engine & ApplicationSets bootstrapping completed successfully!")


if __name__ == "__main__":
    main()
