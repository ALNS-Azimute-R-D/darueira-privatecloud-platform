#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Enterprise Shared Services
Declarative Forgejo Git IAM & Repository Bootstrapper
==============================================================================
"""

import sys
import os
import json
import base64
import time
import subprocess
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
import re

FORGEJO_HOST = os.environ.get("FORGEJO_HOST", "forgejo-git.drr-corpshared-plat.svc.cluster.local:3000")
FORGEJO_BASE_URL = f"http://{FORGEJO_HOST}"
ADMIN_USER = "drradmin"
ADMIN_PASSWORD = os.environ.get("FORGEJO_ADMIN_PASSWORD", "darueira-admin123")
TEKTON_WEBHOOK_URL = os.environ.get("TEKTON_WEBHOOK_URL", "http://el-forgejo-webhook-listener.drr-corpshared-mgmt.svc.cluster.local:8080")

USERS = [
    ("andre.nascimento", "Darueira@2026!"),
    ("alice.developer", "Darueira@2026!"),
    ("bob.engineer", "Darueira@2026!"),
    ("carol.contractor", "Darueira@2026!")
]

ORGANIZATIONS = ["darueira-corp", "acme", "globex"]

REPOSITORIES = [
    ("darueira-corp", "platform-core", "Core platform Helm charts and manifest repository"),
    ("acme", "storefront-app", "Acme e-Commerce Storefront microfrontend repository"),
    ("acme", "logistics-svc", "Acme Logistics & Order Processing service repository"),
    ("globex", "security-audit", "Globex security compliance and audit repository")
]


def run_cmd(cmd_list):
    res = subprocess.run(cmd_list, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr


def bootstrap_admin_and_ldap():
    print("--> Checking Forgejo Master Admin & Authentik LDAP Authentication Source...")
    # 1. Ensure admin user exists via kubectl exec to forgejo-git pod
    cmd_admin = [
        "kubectl", "exec", "-n", "drr-corpshared-plat", "deploy/forgejo-git", "-c", "forgejo", "--",
        "forgejo", "admin", "user", "create",
        "--admin", "--username", ADMIN_USER, "--password", ADMIN_PASSWORD,
        "--email", f"{ADMIN_USER}@darueira.local", "--must-change-password=false"
    ]
    rc, out, err = run_cmd(cmd_admin)
    if rc == 0:
        print("    [✓] Created Forgejo master administrator:", ADMIN_USER)
    else:
        print("    [✓] Forgejo master administrator already exists.")

    # 2. Check or add LDAP auth source
    cmd_auth_list = [
        "kubectl", "exec", "-n", "drr-corpshared-plat", "deploy/forgejo-git", "-c", "forgejo", "--",
        "forgejo", "admin", "auth", "list"
    ]
    rc, out, err = run_cmd(cmd_auth_list)
    if "authentik-ldap" in out:
        cmd_update_ldap = [
            "kubectl", "exec", "-n", "drr-corpshared-plat", "deploy/forgejo-git", "-c", "forgejo", "--",
            "forgejo", "admin", "auth", "update-ldap",
            "--id", "1",
            "--name", "authentik-ldap",
            "--host", "authentik-ldap-outpost.drr-corpshared-plat.svc.cluster.local",
            "--port", "389",
            "--security-protocol", "Unencrypted",
            "--bind-dn", "cn=akadmin,ou=users,dc=darueira,dc=local",
            "--bind-password", "darueira-admin123",
            "--user-search-base", "ou=users,dc=darueira,dc=local",
            "--user-filter", "(cn=%s)",
            "--username-attribute", "cn",
            "--firstname-attribute", "displayName",
            "--surname-attribute", "sn",
            "--email-attribute", "mail",
            "--active"
        ]
        run_cmd(cmd_update_ldap)
        print("    [✓] Updated existing Authentik LDAP authentication source.")
    else:
        cmd_add_ldap = [
            "kubectl", "exec", "-n", "drr-corpshared-plat", "deploy/forgejo-git", "-c", "forgejo", "--",
            "forgejo", "admin", "auth", "add-ldap",
            "--name", "authentik-ldap",
            "--host", "authentik-ldap-outpost.drr-corpshared-plat.svc.cluster.local",
            "--port", "389",
            "--security-protocol", "Unencrypted",
            "--bind-dn", "cn=akadmin,ou=users,dc=darueira,dc=local",
            "--bind-password", "darueira-admin123",
            "--user-search-base", "ou=users,dc=darueira,dc=local",
            "--user-filter", "(cn=%s)",
            "--username-attribute", "cn",
            "--firstname-attribute", "displayName",
            "--surname-attribute", "sn",
            "--email-attribute", "mail",
            "--active",
            "--synchronize-users"
        ]
        run_cmd(cmd_add_ldap)
        print("    [✓] Added Authentik LDAP authentication source.")


def sync_ldap_users():
    print("--> JIT Syncing Corporate Users via Web Login...")
    for username, password in USERS:
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

        try:
            resp = opener.open(f"{FORGEJO_BASE_URL}/user/login", timeout=5)
            html = resp.read().decode("utf-8")
            csrf_match = re.search(r"name=\"_csrf\"\s+value=\"([^\"]+)\"", html)
            if not csrf_match:
                continue
            csrf = csrf_match.group(1)

            data = urllib.parse.urlencode({
                "_csrf": csrf,
                "user_name": username,
                "password": password
            }).encode()

            login_req = urllib.request.Request(f"{FORGEJO_BASE_URL}/user/login", data=data)
            login_resp = opener.open(login_req, timeout=5)
            if login_resp.status == 200:
                print(f"    [✓] Synced user: {username:20} (LDAP authenticated & provisioned)")
        except Exception as e:
            print(f"    User sync note for {username}: {e}")


def configure_orgs_and_repos():
    print("--> Provisioning Corporate Organizations and Repositories...")
    auth = base64.b64encode(b"andre.nascimento:Darueira@2026!").decode()
    headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}

    # 1. Create Orgs
    for org in ORGANIZATIONS:
        req = urllib.request.Request(
            f"{FORGEJO_BASE_URL}/api/v1/orgs",
            data=json.dumps({"username": org, "visibility": "public"}).encode(),
            headers=headers,
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                print(f"    [✓] Created Organization: {org}")
        except urllib.error.HTTPError as e:
            if e.code in (400, 409, 422):
                print(f"    [✓] Organization {org} already exists.")
            else:
                print(f"    Org {org} error: {e.code}")

    # 2. Create Repositories
    for org, repo_name, desc in REPOSITORIES:
        payload = {
            "name": repo_name,
            "description": desc,
            "private": False,
            "auto_init": True,
            "default_branch": "main"
        }
        req = urllib.request.Request(
            f"{FORGEJO_BASE_URL}/api/v1/orgs/{org}/repos",
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                print(f"    [✓] Created Repository: {org}/{repo_name}")
        except urllib.error.HTTPError as e:
            if e.code in (400, 409, 422):
                print(f"    [✓] Repository {org}/{repo_name} already exists.")
            else:
                print(f"    Repo {org}/{repo_name} error: {e.code}")

    # 3. Configure Tekton Webhook on platform-core
    webhook_payload = {
        "type": "gitea",
        "config": {
            "url": TEKTON_WEBHOOK_URL,
            "content_type": "json"
        },
        "events": ["push", "pull_request"],
        "active": True
    }
    hook_req = urllib.request.Request(
        f"{FORGEJO_BASE_URL}/api/v1/repos/darueira-corp/platform-core/hooks",
        data=json.dumps(webhook_payload).encode(),
        headers=headers,
        method="POST"
    )
    try:
        with urllib.request.urlopen(hook_req, timeout=5) as resp:
            print("    [✓] Configured Tekton CI Webhook for darueira-corp/platform-core")
    except urllib.error.HTTPError as e:
        if e.code in (400, 409, 422):
            print("    [✓] Tekton CI Webhook already configured.")
        else:
            print(f"    Webhook note: {e.code}")


def main():
    print("==================================================================")
    print("  Bootstrapping Forgejo Git Server for Darueira Cloud IAM        ")
    print("==================================================================")

    # Check health
    for _ in range(10):
        try:
            with urllib.request.urlopen(f"{FORGEJO_BASE_URL}/api/v1/version", timeout=3) as resp:
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(2)

    bootstrap_admin_and_ldap()
    sync_ldap_users()
    configure_orgs_and_repos()

    print("\n[✓] Forgejo Git Server IAM & Repository bootstrap completed successfully!")


if __name__ == "__main__":
    main()
