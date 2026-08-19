#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Unified Observability & Telemetry Engine
OpenSearch Log Analytics, Fluent Bit, Prometheus, Grafana & Jaeger Bootstrapper
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
OBS_DIR = os.path.join(PROJECT_ROOT, "platform", "kustomize", "base", "corpshared-obs")
APISIX_SCRIPT = os.path.join(SCRIPT_DIR, "bootstrap_apisix_routes.py")


def run_cmd(cmd, check=True):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and res.returncode != 0:
        print(f"    [!] Command failed: {cmd}\n    Stderr: {res.stderr.strip()}")
        raise RuntimeError(f"Command exited with code {res.returncode}: {res.stderr.strip()}")
    return res


def apply_observability_manifests():
    print("--> Applying Observability base manifests (OpenSearch, Fluent Bit, Prometheus, Grafana, Jaeger, OTel)...")
    run_cmd(f"microk8s kubectl apply -f {OBS_DIR}/")
    print("    [✓] Base observability manifests applied successfully")


def update_apisix_oidc_routes():
    print("--> Updating APISIX Gateway Ingress Routes with Keycloak OIDC Security...")
    # Port forward apisix gateway to seed routes
    pf = subprocess.Popen(
        "microk8s kubectl port-forward -n drr-corpshared-plat svc/apisix-gateway 9180:9180",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(2)
    try:
        run_cmd(f"python3 {APISIX_SCRIPT}")
        print("    [✓] APISIX Gateway routes secured with Keycloak OIDC authentication")
    finally:
        pf.terminate()
        pf.wait()


def wait_for_observability_rollout():
    print("--> Waiting for Observability Microservices Rollout and Health...")
    deployments = [
        "opensearch",
        "opensearch-dashboards",
        "prometheus",
        "grafana",
        "jaeger",
        "otel-collector"
    ]
    for dep in deployments:
        run_cmd(f"microk8s kubectl rollout status deployment/{dep} -n drr-corpshared-obs --timeout=90s")
        print(f"    [✓] Deployment '{dep}' is fully ready")


def main():
    print("==================================================================")
    print("  Phase 12: Bootstrapping Unified Observability & Keycloak OIDC   ")
    print("==================================================================")

    apply_observability_manifests()
    update_apisix_oidc_routes()
    wait_for_observability_rollout()

    print("\n[✓] Observability Stack & Keycloak OIDC Integration bootstrap completed successfully!")


if __name__ == "__main__":
    main()
