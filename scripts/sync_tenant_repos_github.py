#!/usr/bin/env python3
"""
==============================================================================
Script: scripts/sync_tenant_repos_github.py
Purpose: Keeps the tenant repositories listed in tenants/<tenant>/repos.yaml both in Forgejo (source of truth,
         drives CI/CD) and in GitHub (off-cluster copy), idempotently.
           mirrors : for every repo with `mirror: true`, creates the private GitHub repo (when missing) and a Forgejo
                     push mirror to it (sync on every commit plus every 8h). Existing mirrors are left alone.
           restore : after a Forgejo loss, recreates every repo in Forgejo from its GitHub copy (git push --mirror)
                     and re-creates the push webhooks (`hook: true`). A repo that already has commits is skipped.
Usage:   kubectl -n drr-corpshared-plat port-forward svc/forgejo-git 3000:3000 &
         python3 scripts/sync_tenant_repos_github.py mirrors|restore [--tenant swfabrik-europe]
Env:     GITHUB_MIRROR_PAT_FILE (~/.github_mirror_pat; fine-grained PAT, never printed), GITHUB_USER (token owner login,
         default x-access-token), FORGEJO_URL (http://127.0.0.1:3000), FORGEJO_USER (drradmin), FORGEJO_PASS
==============================================================================
"""

import base64
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

import yaml

BASE = os.environ.get("FORGEJO_URL", "http://127.0.0.1:3000").rstrip("/")
FUSER = os.environ.get("FORGEJO_USER", "drradmin")
FPASS = os.environ.get("FORGEJO_PASS", "darueira-admin123")
PAT_FILE = os.path.expanduser(os.environ.get("GITHUB_MIRROR_PAT_FILE", "~/.github_mirror_pat"))
GH_USER = os.environ.get("GITHUB_USER", "x-access-token")
HOOK_URL = "http://el-forgejo-webhook-listener.drr-corpshared-mgmt.svc.cluster.local:8080"
HERE = os.path.dirname(os.path.abspath(__file__))


def pat():
    try:
        return open(PAT_FILE).read().strip()
    except OSError:
        sys.exit(f"[ERROR] GitHub token file not found: {PAT_FILE}")


def http(url, method="GET", data=None, auth=None, ok404=False):
    req = urllib.request.Request(url, method=method, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Authorization": auth, "Content-Type": "application/json",
                                          "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        if e.code == 404 and ok404:
            return None
        sys.exit(f"[ERROR] {method} {url.split('?')[0]}: HTTP {e.code} {e.read().decode()[:200]}")


def forgejo(path, method="GET", data=None, ok404=False):
    token = base64.b64encode(f"{FUSER}:{FPASS}".encode()).decode()
    return http(f"{BASE}/api/v1{path}", method, data, f"Basic {token}", ok404)


def github(path, method="GET", data=None, ok404=False):
    return http(f"https://api.github.com{path}", method, data, f"Bearer {pat()}", ok404)


def load(tenant):
    with open(os.path.join(HERE, "..", "tenants", tenant, "repos.yaml")) as f:
        return yaml.safe_load(f)


def ensure_github_repo(full):
    owner, name = full.split("/")
    if github(f"/repos/{full}", ok404=True):
        return False
    # an organization is created through /orgs, a personal account through /user
    org = github(f"/orgs/{owner}", ok404=True)
    github("/orgs/%s/repos" % owner if org else "/user/repos", "POST", {"name": name, "private": True})
    return True


def mirrors(cfg):
    org = cfg["forgejo_org"]
    for r in cfg["repos"]:
        if not r["mirror"]:
            continue
        created = ensure_github_repo(r["github"])
        remote = f"https://github.com/{r['github']}.git"
        have = forgejo(f"/repos/{org}/{r['name']}/push_mirrors") or []
        if any(m["remote_address"] == remote for m in have):
            print(f"    [=] {r['name']} -> {r['github']}: mirror exists")
            continue
        forgejo(f"/repos/{org}/{r['name']}/push_mirrors", "POST",
                {"remote_address": remote, "remote_username": GH_USER, "remote_password": pat(),
                 "interval": "8h0m0s", "sync_on_commit": True})
        print(f"    [+] {r['name']} -> {r['github']}: {'GitHub repo created, ' if created else ''}mirror created")


def git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def restore(cfg):
    org = cfg["forgejo_org"]
    for r in cfg["repos"]:
        name = r["name"]
        if not forgejo(f"/repos/{org}/{name}", ok404=True):
            forgejo(f"/orgs/{org}/repos", "POST", {"name": name, "private": False, "default_branch": "master", "auto_init": False})
        if forgejo(f"/repos/{org}/{name}/commits?limit=1", ok404=True):
            print(f"    [=] {name}: Forgejo already has commits, skipped")
        else:
            src = f"https://{GH_USER}:{pat()}@github.com/{r['github']}.git"
            dst = f"http://{FUSER}:{FPASS}@{BASE.split('://', 1)[1]}/{org}/{name}.git"
            with tempfile.TemporaryDirectory() as tmp:
                if git("clone", "-q", "--mirror", src, tmp + "/m").returncode != 0:
                    print(f"    [!] {name}: cannot clone {r['github']} (does it exist yet?)")
                    continue
                push = git("push", "-q", "--mirror", dst, cwd=tmp + "/m")
                if push.returncode != 0:
                    sys.exit(f"[ERROR] push {name}: {push.stderr.replace(FPASS, '***').replace(pat(), '***')[:300]}")
            print(f"    [+] {name}: restored from {r['github']}")
        if r["hook"]:
            hooks = forgejo(f"/repos/{org}/{name}/hooks") or []
            if not any(h["config"].get("url") == HOOK_URL for h in hooks):
                forgejo(f"/repos/{org}/{name}/hooks", "POST", {"type": "gitea", "active": True, "events": ["push"],
                                                                "config": {"url": HOOK_URL, "content_type": "json"}})
                print(f"    [+] {name}: webhook created")


def main():
    args = [a for a in sys.argv[1:]]
    tenant = args[args.index("--tenant") + 1] if "--tenant" in args else "swfabrik-europe"
    mode = next((a for a in args if a in ("mirrors", "restore")), None)
    if not mode:
        sys.exit(__doc__)
    cfg = load(tenant)
    print(f"--> {mode} ({tenant})")
    {"mirrors": mirrors, "restore": restore}[mode](cfg)


if __name__ == "__main__":
    main()
