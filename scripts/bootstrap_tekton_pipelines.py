#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Continuous Integration & Golden Paths
Declarative Tekton CI/CD Pipelines & EventListener Bootstrapper
==============================================================================
"""

import sys
import os
import subprocess
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
TEKTON_DIR = os.path.join(PROJECT_ROOT, "platform", "gitops", "tekton-pipelines")


def run_cmd(cmd, check=True):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and res.returncode != 0:
        print(f"    [!] Command failed: {cmd}\n    Stderr: {res.stderr.strip()}")
        raise RuntimeError(f"Command exited with code {res.returncode}: {res.stderr.strip()}")
    return res


def configure_tekton_security_and_defaults():
    print("--> Configuring Tekton Pod Security Standards (PSS) & Controller Defaults...")
    # Patch feature-flags
    patch_flags = '{"data":{"set-security-context":"true"}}'
    run_cmd(f"microk8s kubectl patch cm feature-flags -n drr-corpshared-mgmt --type merge -p '{patch_flags}'")

    # Patch config-defaults
    pod_sec = "securityContext:\\n  runAsNonRoot: true\\n  runAsUser: 10001\\n  runAsGroup: 10001\\n  fsGroup: 10001\\n  seccompProfile:\\n    type: RuntimeDefault\\n"
    patch_defaults = f'{{"data":{{"default-pod-template":"{pod_sec}","default-affinity-assistant-pod-template":"{pod_sec}"}}}}'
    run_cmd(f"microk8s kubectl patch cm config-defaults -n drr-corpshared-mgmt --type merge -p '{patch_defaults}'")
    print("    [✓] Tekton feature-flags and config-defaults patched with non-root security contexts")


def apply_tekton_rbac():
    print("--> Applying Tekton Triggers RBAC Roles & Bindings in 'drr-corpshared-mgmt'...")
    rbac_yaml = """
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: tekton-triggers-eventlistener-role
  namespace: drr-corpshared-mgmt
rules:
  - apiGroups: ["tekton.dev"]
    resources: ["tasks", "clustertasks", "taskruns", "pipelines", "pipelineruns"]
    verbs: ["create", "get", "list", "watch", "update", "patch", "delete"]
  - apiGroups: ["triggers.tekton.dev"]
    resources: ["eventlisteners", "triggerbindings", "triggertemplates", "interceptors", "clusterinterceptors"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["configmaps", "secrets", "serviceaccounts", "persistentvolumeclaims", "events"]
    verbs: ["get", "list", "watch", "create", "update", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: tekton-triggers-eventlistener-binding
  namespace: drr-corpshared-mgmt
subjects:
  - kind: ServiceAccount
    name: tekton-triggers-controller
    namespace: drr-corpshared-mgmt
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: tekton-triggers-eventlistener-role
"""
    proc = subprocess.run("microk8s kubectl apply -f -", shell=True, input=rbac_yaml, capture_output=True, text=True, check=True)
    print("    [✓] Applied tekton-triggers-eventlistener-role and rolebinding")


def apply_tekton_manifests():
    print("--> Applying Declarative Tekton Tasks, Pipelines, and Triggers...")
    run_cmd(f"microk8s kubectl apply -n drr-corpshared-mgmt -f {TEKTON_DIR}/")
    print("    [✓] Applied standard-ci-cd-pipeline, tasks, and forgejo-webhook-listener")


def wait_for_controllers():
    print("--> Verifying Tekton Pipelines & Triggers Controllers...")
    run_cmd("microk8s kubectl rollout status deployment/tekton-pipelines-controller -n drr-corpshared-mgmt --timeout=60s")
    run_cmd("microk8s kubectl rollout status deployment/tekton-triggers-controller -n drr-corpshared-mgmt --timeout=60s")
    print("    [✓] Tekton Controllers are healthy and operational")


def main():
    print("==================================================================")
    print("  Phase 10: Bootstrapping Tekton CI/CD & Golden Path Pipelines    ")
    print("==================================================================")

    configure_tekton_security_and_defaults()
    apply_tekton_rbac()
    apply_tekton_manifests()
    wait_for_controllers()

    print("\n[✓] Tekton CI/CD & Golden Path pipelines bootstrapping completed successfully!")


if __name__ == "__main__":
    main()
