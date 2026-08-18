#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Enterprise Shared Services
Forgejo Git Server LDAP IAM, Multi-Tenancy & Webhook Validation Suite
==============================================================================
"""

import sys
import os
import json
import base64
import time
import urllib.request
import urllib.parse
import urllib.error

FORGEJO_HOST = os.environ.get("FORGEJO_HOST", "forgejo-git.drr-corpshared-plat.svc.cluster.local:3000")
FORGEJO_BASE_URL = f"http://{FORGEJO_HOST}"

TEST_USERS = [
    {
        "username": "andre.nascimento",
        "email": "andre.nascimento@darueira.local",
        "password": "Darueira@2026!",
        "expected_admin": True
    },
    {
        "username": "alice.developer",
        "email": "alice.developer@darueira.local",
        "password": "Darueira@2026!",
        "expected_admin": False
    },
    {
        "username": "bob.engineer",
        "email": "bob.engineer@darueira.local",
        "password": "Darueira@2026!",
        "expected_admin": False
    },
    {
        "username": "carol.contractor",
        "email": "carol.contractor@globex.local",
        "password": "Darueira@2026!",
        "expected_admin": False
    }
]

EXPECTED_ORGS = ["darueira-corp", "acme", "globex"]

EXPECTED_REPOS = [
    "darueira-corp/platform-core",
    "acme/storefront-app",
    "acme/logistics-svc",
    "globex/security-audit"
]


def test_user_authentication(user_info):
    username = user_info["username"]
    password = user_info["password"]
    auth = base64.b64encode(f"{username}:{password}".encode()).decode()
    
    url = f"{FORGEJO_BASE_URL}/api/v1/user"
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
    
    with urllib.request.urlopen(req, timeout=20) as resp:
        assert resp.status == 200, f"Expected HTTP 200 for user {username}, got {resp.status}"
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("username") == username, f"Username mismatch: {data.get('username')}"
        assert data.get("email") == user_info["email"], f"Email mismatch: {data.get('email')}"
        if user_info["expected_admin"]:
            assert data.get("is_admin") is True, f"User {username} was expected to be an admin"
        return data


def get_or_create_pat():
    auth = base64.b64encode(b"andre.nascimento:Darueira@2026!").decode()
    token_name = f"val-token-{int(time.time())}"
    token_payload = {
        "name": token_name,
        "scopes": ["all"]
    }
    req = urllib.request.Request(
        f"{FORGEJO_BASE_URL}/api/v1/users/andre.nascimento/tokens",
        data=json.dumps(token_payload).encode(),
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data.get("sha1")


def test_organizations_and_repos(token):
    headers = {"Authorization": f"token {token}"}

    # Verify Orgs
    for org in EXPECTED_ORGS:
        url = f"{FORGEJO_BASE_URL}/api/v1/orgs/{org}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            assert resp.status == 200, f"Org {org} returned {resp.status}"

    # Verify Repos
    for repo_full in EXPECTED_REPOS:
        url = f"{FORGEJO_BASE_URL}/api/v1/repos/{repo_full}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            assert resp.status == 200, f"Repo {repo_full} returned {resp.status}"
            repo_data = json.loads(resp.read().decode("utf-8"))
            assert repo_data.get("full_name") == repo_full, f"Repo name mismatch: {repo_data.get('full_name')}"


def test_git_smart_http_protocol():
    auth = base64.b64encode(b"alice.developer:Darueira@2026!").decode()
    url = f"{FORGEJO_BASE_URL}/acme/storefront-app.git/info/refs?service=git-upload-pack"
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        assert resp.status == 200, f"Smart HTTP returned status {resp.status}"
        ctype = resp.headers.get("Content-Type")
        assert "application/x-git-upload-pack-advertisement" in ctype, f"Invalid Git content-type: {ctype}"
        return ctype


def test_webhook_configuration(token):
    headers = {"Authorization": f"token {token}"}
    url = f"{FORGEJO_BASE_URL}/api/v1/repos/darueira-corp/platform-core/hooks"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        hooks = json.loads(resp.read().decode("utf-8"))
        assert len(hooks) > 0, "No hooks configured on platform-core"
        tekton_hook = [h for h in hooks if "webhook-listener" in h.get("config", {}).get("url", "")]
        assert len(tekton_hook) > 0, "Tekton webhook listener not found in repo hooks"
        return tekton_hook[0].get("config", {}).get("url")


def main():
    print("==================================================================")
    print("  Phase 04: Forgejo Git Server LDAP IAM Validation Suite          ")
    print("==================================================================")

    # 1. User Authentication
    print("\n[1/4] Validating Authentik LDAP User Authentication & Profile Assertion...")
    for user in TEST_USERS:
        u_name = user["username"]
        exp_admin = "Administrator" if user["expected_admin"] else "Standard User"
        print(f"  --> Authenticating {u_name} ({exp_admin})...")
        profile = test_user_authentication(user)
        print(f"      [✓] Authenticated! ID: {profile.get('id')}, Email: {profile.get('email')}, Admin: {profile.get('is_admin')}")
        time.sleep(0.3)

    # Generate test token
    token = get_or_create_pat()

    # 2. Multi-Tenant Organizations & Repositories
    print("\n[2/4] Validating Multi-Tenant Organizations & Starter Repositories...")
    test_organizations_and_repos(token)
    print(f"      [✓] All {len(EXPECTED_ORGS)} organizations verified: {EXPECTED_ORGS}")
    print(f"      [✓] All {len(EXPECTED_REPOS)} repositories verified: {EXPECTED_REPOS}")

    # 3. Git Smart HTTP Protocol
    print("\n[3/4] Validating Git Smart HTTP (:3000) Protocol & Authentication...")
    ctype = test_git_smart_http_protocol()
    print(f"      [✓] Git upload-pack advertisement verified ({ctype})")

    # 4. Tekton CI Webhook Integration
    print("\n[4/4] Validating Tekton CI Webhook Dispatch Configuration...")
    hook_url = test_webhook_configuration(token)
    print(f"      [✓] Tekton EventListener Webhook active: {hook_url}")

    print("\n==================================================================")
    print("  [✓✓✓] ALL PHASE 04 FORGEJO GIT IAM VALIDATION TESTS PASSED!     ")
    print("==================================================================")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[✗] Validation failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
