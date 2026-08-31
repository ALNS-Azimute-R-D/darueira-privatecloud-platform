#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Tenant CI/CD Lifecycle & PR Promotion Script
Follows strict Platform Standards:
1. Feature branch created and pushed
2. Pull Request created via Forgejo API
3. PR merged into protected 'master' branch
4. Merge triggers Tekton CI/CD pipeline via Webhook
5. Polyglot Build -> Kaniko Push to Nexus (YYYY.MMDD.HHmmSS tag) -> ArgoCD Sync
==============================================================================
"""

import sys
import os
import json
import time
import base64
import subprocess
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
TENANT_WORKSPACE = os.path.join(PROJECT_ROOT, "workspace", "platf-bizz-apps", "swfabrik-europe")

FORGEJO_ADMIN_USER = "drradmin"
FORGEJO_ADMIN_PASS = "darueira-admin123"
TENANT_NAME = "swfabrik-europe"

MODIFIED_PROJECTS = [
    "food-market-03-service",
    "food-market-04-service",
    "food-market-01-service",
    "food-market-02-service",
    "food-market-05-service",
    "food-market-06-service",
    "app-food-market-00-mfe",
    "legaltech-caseforce-solutions",
]


def get_forgejo_host():
    cmd = "microk8s kubectl get pod -n drr-corpshared-plat -l app.kubernetes.io/name=forgejo-git -o jsonpath='{.items[0].status.podIP}'"
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    pod_ip = res.stdout.strip()
    if pod_ip:
        return f"{pod_ip}:3000"
    return "10.152.183.187:3000"


def get_forgejo_auth_header():
    auth = base64.b64encode(f"{FORGEJO_ADMIN_USER}:{FORGEJO_ADMIN_PASS}".encode()).decode()
    return {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}


def run_cmd(cmd, cwd=None, check=True):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    if check and res.returncode != 0:
        print(f"    [!] Command failed in {cwd or '.'}: {cmd}\n    Stderr: {res.stderr.strip()}")
        raise RuntimeError(f"Command failed: {cmd}")
    return res


def process_project(repo_name):
    repo_path = os.path.join(TENANT_WORKSPACE, repo_name)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    branch_name = f"feature/keycloak-coarse-authz-{timestamp}"
    forgejo_host = get_forgejo_host()

    print("\n" + "=" * 80)
    print(f"  --> Processing CI/CD PR for: {TENANT_NAME}/{repo_name}")
    print(f"      Branch: {branch_name}")
    print(f"      Target: master (protected)")
    print("=" * 80)

    # Check uncommitted changes
    st = run_cmd("git status -s", cwd=repo_path, check=False).stdout.strip()
    if not st:
        print(f"    [i] No local changes in {repo_name}. Skipping.")
        return None

    # 1. Create feature branch
    print(f"--> 1. Creating and switching to branch '{branch_name}'...")
    run_cmd(f"git checkout -b {branch_name}", cwd=repo_path)

    # 2. Stage and commit
    print("--> 2. Staging all changes and committing...")
    run_cmd("git add -A", cwd=repo_path)
    msg = f"feat(authz): configure Keycloak OIDC authentication & coarse-grained roles [{timestamp}]"
    run_cmd(f"git commit -m '{msg}'", cwd=repo_path)

    # 3. Push branch to Forgejo
    print(f"--> 3. Pushing branch '{branch_name}' to Forgejo origin...")
    run_cmd(f"git push -u origin {branch_name}", cwd=repo_path)

    # 4. Open Pull Request
    print("--> 4. Opening Pull Request via Forgejo API...")
    headers = get_forgejo_auth_header()
    pr_payload = {
        "base": "master",
        "head": branch_name,
        "title": f"feat(authz): Keycloak OIDC Authentication & Coarse-Grained Roles ({timestamp})",
        "body": f"Automated CI/CD promotion for Mission 3: Keycloak tenant realm integration, JWT validation and coarse-grained role/group mapping."
    }
    pr_req = urllib.request.Request(
        f"http://{forgejo_host}/api/v1/repos/{TENANT_NAME}/{repo_name}/pulls",
        data=json.dumps(pr_payload).encode(),
        headers=headers,
        method="POST"
    )
    with urllib.request.urlopen(pr_req, timeout=15) as resp:
        pr_data = json.loads(resp.read().decode())
        pr_number = pr_data["number"]
        print(f"    [✓] Created PR #{pr_number}: '{pr_data['title']}'")

    time.sleep(2)

    # 5. Merge Pull Request
    print(f"--> 5. Merging PR #{pr_number} into protected 'master'...")
    merge_payload = {
        "Do": "merge",
        "MergeTitleField": f"feat(authz): Keycloak OIDC Authentication & Coarse-Grained Roles (#{pr_number})",
        "MergeMessageField": f"Merge branch '{branch_name}' into master"
    }
    merge_req = urllib.request.Request(
        f"http://{forgejo_host}/api/v1/repos/{TENANT_NAME}/{repo_name}/pulls/{pr_number}/merge",
        data=json.dumps(merge_payload).encode(),
        headers=headers,
        method="POST"
    )
    with urllib.request.urlopen(merge_req, timeout=15) as resp:
        print(f"    [✓] Successfully merged PR #{pr_number} into 'master'!")

    # 6. Align local master branch and clean up feature branch
    print(f"--> 6. Resetting local branch to 'master'...")
    run_cmd("git checkout master", cwd=repo_path)
    run_cmd("git pull origin master", cwd=repo_path)
    run_cmd(f"git branch -D {branch_name}", cwd=repo_path, check=False)
    run_cmd(f"git push origin --delete {branch_name}", cwd=repo_path, check=False)

    return repo_name


def main():
    print("================================================================================")
    print("  Darueira Private Cloud Platform - Mission 3 CI/CD & PR Promotion")
    print("  Standards:")
    print("    - Main branch: master (protected)")
    print("    - PR-driven merge via Forgejo API")
    print("    - Automated Tekton CI/CD PipelineRun triggering")
    print("    - OCI image push to Nexus (localhost:8082 / nexus-oss)")
    print("    - Image Tagging: YYYY.MMDD.HHmmSS")
    print("================================================================================")

    processed = []
    for proj in MODIFIED_PROJECTS:
        res = process_project(proj)
        if res:
            processed.append(res)
            time.sleep(2)

    print("\n" + "=" * 80)
    print(f"  [✓] All {len(processed)} repositories merged into 'master'!")
    print("=" * 80)


if __name__ == "__main__":
    main()
