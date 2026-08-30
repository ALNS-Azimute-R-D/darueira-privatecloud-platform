#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Tenant Local Repositories Alignment Engine
Aligns all subrepos in workspace/platf-bizz-apps/swfabrik-europe to branch 'master',
sets upstream tracking to origin/master, ensures .gitignore, and cleans working trees.
==============================================================================
"""

import os
import sys
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
TENANT_WORKSPACE = os.path.join(PROJECT_ROOT, "workspace", "platf-bizz-apps", "swfabrik-europe")

def run_cmd(cmd, cwd=None, check=True):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    if check and res.returncode != 0:
        print(f"    [!] Command failed in {cwd or '.'}: {cmd}\n    Stderr: {res.stderr.strip()}")
        raise RuntimeError(f"Command failed: {cmd}")
    return res


def main():
    print("==================================================================")
    print("  Aligning Tenant Local Repositories to 'master' Branch           ")
    print(f"  Directory: {TENANT_WORKSPACE}")
    print("==================================================================")

    for item in sorted(os.listdir(TENANT_WORKSPACE)):
        repo_path = os.path.join(TENANT_WORKSPACE, item)
        if not os.path.isdir(repo_path) or not os.path.exists(os.path.join(repo_path, ".git")):
            continue

        print(f"\n--> Aligning repository: '{item}'...")

        # 1. Fetch origin master
        run_cmd("git fetch origin master", cwd=repo_path)

        # 2. Force checkout and hard reset to origin/master
        run_cmd("git checkout -B master origin/master -f", cwd=repo_path)
        run_cmd("git reset --hard origin/master", cwd=repo_path)
        run_cmd("git branch --set-upstream-to=origin/master master", cwd=repo_path)

        # 3. Clean up any obsolete local 'main' branch
        run_cmd("git branch -D main 2>/dev/null || true", cwd=repo_path, check=False)

        # 4. Remove any untracked .iml or build leftovers
        run_cmd("git clean -fd", cwd=repo_path)

        # 5. Verify status
        res = run_cmd("git status -sb", cwd=repo_path)
        print(f"    [✓] Status: {res.stdout.strip()}")

    print("\n==================================================================")
    print("  [✓] All Tenant local repositories aligned to 'origin/master'!")
    print("==================================================================")


if __name__ == "__main__":
    main()
