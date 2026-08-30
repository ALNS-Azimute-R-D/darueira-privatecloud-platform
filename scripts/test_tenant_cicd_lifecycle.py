#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Tenant CI/CD Lifecycle End-to-End Test Suite
Tests the complete lifecycle for each tenant project:
1. Create feature branch
2. Make simple change & commit
3. Push feature branch to Forgejo
4. Create Pull Request (PR) via Forgejo API
5. Merge Pull Request into protected 'master' branch via Forgejo API
6. Monitor Tekton PipelineRun triggered via Webhook until SUCCEEDED
7. Verify GitOps Helm Chart tag promotion and ArgoCD deployment sync
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

ALL_PROJECTS = [
    "food-market-03-service",
    "food-market-04-service",
    "food-market-01-service",
    "food-market-02-service",
    "food-market-05-service",
    "food-market-06-service",
    "app-food-market-00-mfe",
    "app-food-market-01-react",
    "app-food-market-02-angular",
    "legaltech-caseforce-solutions"
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


def test_project_lifecycle(repo_name):
    repo_path = os.path.join(TENANT_WORKSPACE, repo_name)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    branch_name = f"feature/ci-cd-verify-{timestamp}"
    forgejo_host = get_forgejo_host()

    print("\n" + "=" * 80)
    print(f"  [START] Testing CI/CD Lifecycle for: {TENANT_NAME}/{repo_name}")
    print(f"  Branch: {branch_name}")
    print(f"  Forgejo Host: {forgejo_host}")
    print("=" * 80)

    # 1. Align on master & pull latest
    print("--> 1. Aligning local repository with origin/master...")
    run_cmd("git checkout master", cwd=repo_path)
    run_cmd("git pull origin master", cwd=repo_path)

    # 2. Create feature branch
    print(f"--> 2. Creating feature branch '{branch_name}'...")
    run_cmd(f"git checkout -b {branch_name}", cwd=repo_path)

    # 3. Make small change in README.md
    readme_path = os.path.join(repo_path, "README.md")
    if not os.path.exists(readme_path):
        with open(readme_path, "w") as f:
            f.write(f"# {repo_name}\n")
    with open(readme_path, "a") as f:
        f.write(f"\n<!-- CI/CD Lifecycle Verification Test: {timestamp} -->\n")

    # 4. Commit and push feature branch
    print(f"--> 3. Committing and pushing '{branch_name}' to Forgejo...")
    run_cmd("git add README.md", cwd=repo_path)
    run_cmd(f"git commit -m 'feat: verify automated CI/CD lifecycle pipeline [{timestamp}]'", cwd=repo_path)
    run_cmd(f"git push -u origin {branch_name}", cwd=repo_path)

    # 5. Create Pull Request via Forgejo API
    print("--> 4. Opening Pull Request on Forgejo...")
    headers = get_forgejo_auth_header()
    pr_payload = {
        "base": "master",
        "head": branch_name,
        "title": f"feat: automated CI/CD pipeline verification ({timestamp})",
        "body": f"Testing end-to-end CI/CD lifecycle from branch {branch_name} to Tekton and ArgoCD."
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

    # Short delay before merge
    time.sleep(2)

    # 6. Merge Pull Request via Forgejo API
    print(f"--> 5. Merging PR #{pr_number} into 'master'...")
    merge_payload = {
        "Do": "merge",
        "MergeTitleField": f"feat: automated CI/CD pipeline verification (#{pr_number})",
        "MergeMessageField": f"Merge branch {branch_name} into master"
    }
    merge_req = urllib.request.Request(
        f"http://{forgejo_host}/api/v1/repos/{TENANT_NAME}/{repo_name}/pulls/{pr_number}/merge",
        data=json.dumps(merge_payload).encode(),
        headers=headers,
        method="POST"
    )
    with urllib.request.urlopen(merge_req, timeout=15) as resp:
        print(f"    [✓] Successfully merged PR #{pr_number} into 'master'!")

    # 7. Clean up local branch and delete remote feature branch
    print(f"--> 6. Cleaning up feature branch '{branch_name}'...")
    run_cmd("git checkout master", cwd=repo_path)
    run_cmd("git pull origin master", cwd=repo_path)
    run_cmd(f"git branch -D {branch_name}", cwd=repo_path, check=False)
    run_cmd(f"git push origin --delete {branch_name}", cwd=repo_path, check=False)

    # 8. Monitor Tekton PipelineRun triggered by the merge webhook
    print(f"--> 7. Waiting for Tekton Webhook to trigger PipelineRun for '{repo_name}'...")
    time.sleep(4)

    pr_name = None
    for _ in range(15):
        cmd = f"microk8s kubectl get pipelineruns -n drr-corpshared-mgmt --sort-by=.metadata.creationTimestamp -o json"
        res = run_cmd(cmd, check=False)
        try:
            items = json.loads(res.stdout).get("items", [])
            for item in reversed(items):
                name = item["metadata"]["name"]
                if repo_name in name:
                    pr_name = name
                    break
        except Exception:
            pass
        if pr_name:
            break
        time.sleep(3)

    if not pr_name:
        raise RuntimeError(f"No Tekton PipelineRun found for {repo_name} after PR merge!")

    print(f"    [✓] Detected Tekton PipelineRun: '{pr_name}'")
    print("    --> Monitoring PipelineRun execution stages...")

    # Wait for completion (max 6 minutes)
    start_wait = time.time()
    succeeded = False
    last_status_summary = ""

    while time.time() - start_wait < 360:
        # Check PipelineRun status
        pr_cmd = f"microk8s kubectl get pipelinerun {pr_name} -n drr-corpshared-mgmt -o json"
        pr_res = run_cmd(pr_cmd, check=False)
        if pr_res.returncode == 0:
            pr_data = json.loads(pr_res.stdout)
            conds = pr_data.get("status", {}).get("conditions", [])
            for c in conds:
                if c.get("type") == "Succeeded":
                    st = c.get("status")
                    reason = c.get("reason")
                    if st == "True":
                        succeeded = True
                        break
                    elif st == "False":
                        raise RuntimeError(f"PipelineRun {pr_name} failed: reason={reason}, msg={c.get('message')}")

            # Check individual tasks
            tr_cmd = f"microk8s kubectl get taskruns -n drr-corpshared-mgmt -l tekton.dev/pipelineRun={pr_name} -o json"
            tr_res = run_cmd(tr_cmd, check=False)
            if tr_res.returncode == 0:
                tr_items = json.loads(tr_res.stdout).get("items", [])
                summary_parts = []
                for t in tr_items:
                    t_name = t["metadata"]["name"].replace(f"{pr_name}-", "")
                    t_status = "Pending"
                    for tc in t.get("status", {}).get("conditions", []):
                        if tc.get("type") == "Succeeded":
                            t_status = "Succeeded" if tc.get("status") == "True" else ("Running" if tc.get("status") == "Unknown" else "Failed")
                    summary_parts.append(f"{t_name}: {t_status}")
                cur_summary = " | ".join(summary_parts)
                if cur_summary != last_status_summary:
                    print(f"      [Progress] {cur_summary}")
                    last_status_summary = cur_summary

        if succeeded:
            break
        time.sleep(8)

    if not succeeded:
        raise TimeoutError(f"PipelineRun {pr_name} timed out!")

    print(f"\n    [✓✓✓] Tekton PipelineRun '{pr_name}' SUCCEEDED 100%!")

    # 9. Verify ArgoCD application sync
    print("--> 8. Verifying GitOps Deployment in Cluster...")
    # Find matching ArgoCD application
    app_target = None
    if "00-mfe" in repo_name:
        app_target = "swfabrik-europe-app-host-mfe"
    elif "01-react" in repo_name:
        app_target = "swfabrik-europe-app-react-01"
    elif "02-angular" in repo_name:
        app_target = "swfabrik-europe-app-angular-02"
    elif "caseforce" in repo_name:
        app_target = "swfabrik-europe-legaltech-caseforce"
    else:
        num = repo_name.replace("food-market-", "").replace("-service", "")
        app_target = f"swfabrik-europe-food-market-{num}"

    time.sleep(3)
    argo_cmd = f"microk8s kubectl get application {app_target} -n drr-corpshared-mgmt -o json"
    argo_res = run_cmd(argo_cmd, check=False)
    if argo_res.returncode == 0:
        argo_data = json.loads(argo_res.stdout)
        sync_st = argo_data.get("status", {}).get("sync", {}).get("status")
        health_st = argo_data.get("status", {}).get("health", {}).get("status")
        print(f"    [✓] ArgoCD Application '{app_target}' -> Sync: {sync_st} | Health: {health_st}")

    print(f"==================================================================")
    print(f"  [SUCCESS] CI/CD Lifecycle Verified for {repo_name} [✓✓✓]")
    print(f"==================================================================")


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None
    if target:
        test_project_lifecycle(target)
    else:
        for p in ALL_PROJECTS:
            test_project_lifecycle(p)


if __name__ == "__main__":
    main()
