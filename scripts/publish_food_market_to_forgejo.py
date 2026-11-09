#!/usr/bin/env python3
"""
==============================================================================
Script: scripts/publish_food_market_to_forgejo.py
Purpose: Idempotently publishes the playground projects of tenant swfabrik-europe from this repository
         (apps/tenant-playground-repos/) to the in-cluster Forgejo. GitHub keeps the sources; Forgejo is derived:
           - the source repo `<project>` (build output and IDE files are left out),
           - the chart repo `<project>-chart`. Its `values-dev-green.yaml` is runtime state (Tekton rewrites the image
             tag after each build), so a copy already in Forgejo is kept and never overwritten; it is only seeded
             when missing,
           - with --hooks, the push webhook to the Tekton EventListener (this is what starts the CI/CD build).
         A repo that already exists is updated with one commit, only when its content changed. Do not commit to these
         Forgejo repos by hand: the next run overwrites it. Edit under apps/tenant-playground-repos/ and publish.
Usage:   kubectl -n drr-corpshared-plat port-forward svc/forgejo-git 3000:3000 &
         python3 scripts/publish_food_market_to_forgejo.py [--hooks] [project ...]
Env:     FORGEJO_URL (http://127.0.0.1:3000), FORGEJO_USER (drradmin), FORGEJO_PASS, FORGEJO_ORG (swfabrik-europe)
==============================================================================
"""

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

BASE = os.environ.get("FORGEJO_URL", "http://127.0.0.1:3000").rstrip("/")
USER = os.environ.get("FORGEJO_USER", "drradmin")
PASS = os.environ.get("FORGEJO_PASS", "darueira-admin123")
ORG = os.environ.get("FORGEJO_ORG", "swfabrik-europe")
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "apps", "tenant-playground-repos")
HOOK_URL = "http://el-forgejo-webhook-listener.drr-corpshared-mgmt.svc.cluster.local:8080"
PROJECTS = [
    "food-market-01-service", "food-market-02-service", "food-market-03-service",
    "food-market-04-service", "food-market-05-service", "food-market-06-service",
    "app-food-market-00-mfe", "app-food-market-01-react", "app-food-market-02-angular",
]
SKIP_DIRS = {"node_modules", "target", "dist", "bin", "obj", ".git", ".idea", "__pycache__", ".gradle"}
SKIP_SUFFIXES = (".iml",)
RUNTIME_STATE = "values-dev-green.yaml"


def api(path, method="GET", data=None):
    token = base64.b64encode(f"{USER}:{PASS}".encode()).decode()
    req = urllib.request.Request(f"{BASE}/api/v1{path}", method=method,
                                 data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        if e.code == 404 and method == "GET":
            return 404, None
        sys.exit(f"[ERROR] {method} {path}: HTTP {e.code} {e.read().decode()[:200]}")


def ensure_repo(name):
    if api(f"/repos/{ORG}/{name}")[0] == 404:
        api(f"/orgs/{ORG}/repos", "POST", {"name": name, "private": False, "default_branch": "master", "auto_init": False})
        print(f"    [+] repo {ORG}/{name} created")


def git(*args, cwd):
    res = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return res


def sync_repo(name, src_dir):
    """Makes the repo content equal to src_dir (minus skipped paths) with one commit when something changed."""
    remote = f"http://{USER}:{PASS}@{BASE.split('://', 1)[1]}/{ORG}/{name}.git"
    with tempfile.TemporaryDirectory() as tmp:
        work = os.path.join(tmp, "w")
        if git("clone", "-q", remote, work, cwd=tmp).returncode != 0 or not os.path.isdir(os.path.join(work, ".git")):
            os.makedirs(work, exist_ok=True)
            git("init", "-q", "-b", "master", cwd=work)
            git("remote", "add", "origin", remote, cwd=work)
        keep = {}
        if name.endswith("-chart") and os.path.isfile(os.path.join(work, RUNTIME_STATE)):
            keep[RUNTIME_STATE] = open(os.path.join(work, RUNTIME_STATE), "rb").read()
        for entry in os.listdir(work):  # wipe the working tree except .git, then copy the source
            if entry != ".git":
                path = os.path.join(work, entry)
                shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
        for dirpath, dirnames, filenames in os.walk(src_dir):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            rel = os.path.relpath(dirpath, src_dir)
            os.makedirs(os.path.join(work, rel), exist_ok=True)
            for f in filenames:
                if not f.endswith(SKIP_SUFFIXES):
                    shutil.copy2(os.path.join(dirpath, f), os.path.join(work, rel, f))
        for rel, content in keep.items():  # runtime state written by Tekton wins over the seed in this repository
            with open(os.path.join(work, rel), "wb") as f:
                f.write(content)
        git("add", "-A", cwd=work)
        if git("status", "--porcelain", cwd=work).stdout.strip() == "":
            print(f"    [=] {name}: already up to date")
            return False
        git("-c", "user.name=Darueira Platform", "-c", "user.email=platform@darueira.local",
            "commit", "-q", "-m", "chore: import from the platform workspace [skip ci]" if name.endswith("-chart")
            else "chore: import from the platform workspace", cwd=work)
        push = git("push", "-q", "origin", "HEAD:master", cwd=work)
        if push.returncode != 0:
            sys.exit(f"[ERROR] push {name}: {push.stderr.strip()[:300].replace(PASS, '***')}")
        print(f"    [+] {name}: pushed")
        return True


def ensure_hook(name):
    _, hooks = api(f"/repos/{ORG}/{name}/hooks")
    if any(h["config"].get("url") == HOOK_URL for h in hooks or []):
        print(f"    [=] webhook of {name} exists")
        return
    api(f"/repos/{ORG}/{name}/hooks", "POST", {
        "type": "gitea", "active": True, "events": ["push"],
        "config": {"url": HOOK_URL, "content_type": "json"}})
    print(f"    [+] webhook of {name} created")


def main():
    hooks = "--hooks" in sys.argv
    wanted = [a for a in sys.argv[1:] if not a.startswith("--")] or PROJECTS
    for project in wanted:
        print(f"--> {project}")
        for repo, folder in ((f"{project}-chart", os.path.join(ROOT, f"{project}-chart")), (project, os.path.join(ROOT, project))):
            ensure_repo(repo)
            sync_repo(repo, folder)
        if hooks:
            ensure_hook(project)


if __name__ == "__main__":
    main()
