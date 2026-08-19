#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Zero Trust In-Pod Interception Sidecars
Declarative Envoy PEP & OPA PDP Sidecar Bootstrapper
==============================================================================
"""

import sys
import os
import subprocess
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
KUSTOMIZE_TENANT_BASE = os.path.join(PROJECT_ROOT, "platform", "kustomize", "base", "tnt-tenant-base")


def run_cmd(cmd, check=True):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and res.returncode != 0:
        print(f"    [!] Command failed: {cmd}\n    Stderr: {res.stderr.strip()}")
        raise RuntimeError(f"Command exited with code {res.returncode}: {res.stderr.strip()}")
    return res


def bootstrap_sidecar_configmaps():
    print("--> Bootstrapping Envoy PEP and OPA PDP ConfigMaps in tenant namespaces...")
    envoy_cm = os.path.join(KUSTOMIZE_TENANT_BASE, "envoy-sidecar-configmap.yaml")
    opa_cm = os.path.join(KUSTOMIZE_TENANT_BASE, "opa-policy-configmap.yaml")

    for ns in ["drr-tnt-acme", "drr-tnt-base-template"]:
        run_cmd(f"microk8s kubectl apply -n {ns} -f {envoy_cm} -f {opa_cm}")
        print(f"    [✓] Applied envoy-sidecar-config & opa-policy-config in namespace '{ns}'")


def deploy_tenant_workloads():
    print("--> Deploying protected tenant workload with Envoy PEP & OPA PDP sidecars...")
    workload_manifest = os.path.join(KUSTOMIZE_TENANT_BASE, "acme-storefront-app.yaml")
    run_cmd(f"microk8s kubectl apply -n drr-tnt-acme -f {workload_manifest}")
    print("    [✓] Applied acme-storefront-app deployment & service in namespace 'drr-tnt-acme'")

    print("--> Waiting for acme-storefront-app (3/3 containers: app, envoy-pep, opa-pdp) to be Ready...")
    run_cmd("microk8s kubectl rollout status deployment/acme-storefront-app -n drr-tnt-acme --timeout=90s")
    print("    [✓] acme-storefront-app is healthy and running with Envoy PEP & OPA PDP sidecars!")


def main():
    print("==================================================================")
    print("  Phase 08: Bootstrapping Envoy PEP & OPA PDP Interception Sidecars")
    print("==================================================================")

    bootstrap_sidecar_configmaps()
    deploy_tenant_workloads()

    print("\n[✓] Envoy PEP & OPA PDP sidecar bootstrapping completed successfully!")


if __name__ == "__main__":
    main()
