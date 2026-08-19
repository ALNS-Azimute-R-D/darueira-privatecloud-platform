#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Core Platform Microservices & Operator
Bootstrapper for drr-tenant-svc, drr-iam-authz-svc, drr-env-orchestrator-svc,
darueira-operator and drr-ctlr-cli Developer CLI
==============================================================================
"""

import sys
import os
import subprocess
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))


def run_cmd(cmd, check=True):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT)
    if check and res.returncode != 0:
        print(f"    [!] Command failed: {cmd}\n    Stderr: {res.stderr.strip()}")
        raise RuntimeError(f"Command exited with code {res.returncode}: {res.stderr.strip()}")
    return res


def build_cli():
    print("--> Building drr-ctlr-cli binary...")
    run_cmd("mkdir -p bin apps/drr-ctlr-cli/bin")
    run_cmd("cd apps/drr-ctlr-cli && CGO_ENABLED=0 go build -o ../../bin/drr-ctlr-cli ./main.go")
    run_cmd("cp bin/drr-ctlr-cli apps/drr-ctlr-cli/bin/drr-ctlr-cli")
    print("    [✓] drr-ctlr-cli binary compiled to bin/drr-ctlr-cli")


def apply_manifests():
    print("--> Applying Core Platform Services and Operator manifests...")
    run_cmd("microk8s kubectl apply -f platform/kustomize/base/corpshared-plat/iam-authz-svc.yaml")
    run_cmd("microk8s kubectl apply -f platform/kustomize/base/corpshared-plat/tenant-svc.yaml")
    run_cmd("microk8s kubectl apply -f platform/kustomize/base/corpshared-mgmt/env-orchestrator-svc.yaml")
    run_cmd("microk8s kubectl apply -f platform/kustomize/base/corpshared-mgmt/darueira-operator.yaml")
    print("    [✓] Manifests applied successfully")


def wait_for_rollouts():
    print("--> Waiting for Microservices and Operator Deployments Rollout...")
    services = [
        ("drr-corpshared-plat", "drr-iam-authz-svc"),
        ("drr-corpshared-plat", "drr-tenant-svc"),
        ("drr-corpshared-mgmt", "drr-env-orchestrator-svc"),
        ("drr-corpshared-mgmt", "darueira-operator"),
    ]
    for ns, dep in services:
        run_cmd(f"microk8s kubectl rollout status deployment/{dep} -n {ns} --timeout=60s")
        print(f"    [✓] {dep} in {ns} is fully operational")


def main():
    print("==================================================================")
    print("  Phase 13: Bootstrapping Core Platform Microservices & Operator   ")
    print("==================================================================")

    build_cli()
    apply_manifests()
    wait_for_rollouts()

    print("\n[✓] Phase 13: Core Platform Microservices & Operator bootstrap completed!")


if __name__ == "__main__":
    main()
