#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Enterprise Shared Services
Forgejo Git Server Keycloak OIDC IAM, Multi-Tenancy & Webhook Validation Suite
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
ADMIN_USER = "drradmin"
ADMIN_PASSWORD = os.environ.get("FORGEJO_ADMIN_PASSWORD", "darueira-admin123")

KEYCLOAK_BASE_URL = os.environ.get("KEYCLOAK_BASE_URL", "http://keycloak.drr-corpshared-plat.svc.cluster.local:8080")
KEYCLOAK_ADMIN_USER = os.environ.get("KEYCLOAK_ADMIN_USER", "admin")
KEYCLOAK_ADMIN_PASS = os.environ.get("KEYCLOAK_ADMIN_PASS", "admin123-dev")
REALM_NAME = "darueira-platform-svcs"
FORGEJO_CLIENT_ID = "forgejo-git"
FORGEJO_CLIENT_SECRET = "darueira-forgejo-secret-2026"

TEST_USERS = [
    {
        "username": "andre.nascimento",
        "email": "andre.nascimento@darueira.local",
        "password": "Darueira@2026!",
        "expected_tenant": "darueira-corp",
        "expected_admin": True
    },
    {
        "username": "alice.developer",
        "email": "alice.developer@darueira.local",
        "password": "Darueira@2026!",
        "expected_tenant": "acme",
        "expected_admin": False
    },
    {
        "username": "bob.engineer",
        "email": "bob.engineer@darueira.local",
        "password": "Darueira@2026!",
        "expected_tenant": "acme",
        "expected_admin": False
    },
    {
        "username": "carol.contractor",
        "email": "carol.contractor@globex.local",
        "password": "Darueira@2026!",
        "expected_tenant": "globex",
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


def test_keycloak_oidc_client():
    # 1. Admin Token
    data = urllib.parse.urlencode({
        "client_id": "admin-cli",
        "username": KEYCLOAK_ADMIN_USER,
        "password": KEYCLOAK_ADMIN_PASS,
        "grant_type": "password"
    }).encode("utf-8")
    req = urllib.request.Request(f"{KEYCLOAK_BASE_URL}/realms/master/protocol/openid-connect/token", data=data)
    with urllib.request.urlopen(req, timeout=30) as resp:
        token = json.loads(resp.read().decode("utf-8"))["access_token"]

    # 2. Get Client
    headers = {"Authorization": f"Bearer {token}"}
    req_client = urllib.request.Request(f"{KEYCLOAK_BASE_URL}/admin/realms/{REALM_NAME}/clients?clientId={FORGEJO_CLIENT_ID}", headers=headers)
    with urllib.request.urlopen(req_client, timeout=30) as resp:
        clients = json.loads(resp.read().decode("utf-8"))
        assert len(clients) > 0, f"Keycloak client '{FORGEJO_CLIENT_ID}' not found in realm '{REALM_NAME}'"
        c = clients[0]
        assert c.get("enabled") is True, f"Keycloak client '{FORGEJO_CLIENT_ID}' is disabled"
        assert c.get("protocol") == "openid-connect", f"Invalid protocol: {c.get('protocol')}"
        return c


def test_user_oidc_authentication(user_info):
    username = user_info["username"]
    password = user_info["password"]

    # 1. Direct Access Grants via Keycloak Token Endpoint
    data = urllib.parse.urlencode({
        "client_id": FORGEJO_CLIENT_ID,
        "client_secret": FORGEJO_CLIENT_SECRET,
        "username": username,
        "password": password,
        "grant_type": "password",
        "scope": "openid email profile"
    }).encode("utf-8")

    token_url = f"{KEYCLOAK_BASE_URL}/realms/{REALM_NAME}/protocol/openid-connect/token"
    req = urllib.request.Request(token_url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        assert resp.status == 200, f"Failed Keycloak token acquisition for {username}: HTTP {resp.status}"
        tokens = json.loads(resp.read().decode("utf-8"))
        access_token = tokens["access_token"]

    # 2. Assert Claims via UserInfo Endpoint
    userinfo_url = f"{KEYCLOAK_BASE_URL}/realms/{REALM_NAME}/protocol/openid-connect/userinfo"
    req_ui = urllib.request.Request(userinfo_url, headers={"Authorization": f"Bearer {access_token}"})
    with urllib.request.urlopen(req_ui, timeout=30) as resp:
        assert resp.status == 200, f"UserInfo endpoint failed for {username}"
        userinfo = json.loads(resp.read().decode("utf-8"))
        assert userinfo.get("preferred_username") == username, f"Username mismatch: {userinfo.get('preferred_username')}"
        assert userinfo.get("email") == user_info["email"], f"Email mismatch: {userinfo.get('email')}"
        assert userinfo.get("tenant") == user_info["expected_tenant"], f"Tenant claim mismatch: {userinfo.get('tenant')}"
        return userinfo


def test_forgejo_oauth_redirect():
    url = f"{FORGEJO_BASE_URL}/user/oauth2/keycloak-oidc"
    req = urllib.request.Request(url)

    class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
        def http_error_302(self, req, fp, code, msg, headers):
            return fp
        def http_error_307(self, req, fp, code, msg, headers):
            return fp

    opener = urllib.request.build_opener(NoRedirectHandler)
    resp = opener.open(req, timeout=30)
    location = resp.headers.get("Location")
    assert location, "No Location header found in OAuth redirect response"
    assert "protocol/openid-connect/auth" in location, f"Invalid OAuth redirect location: {location}"
    assert f"client_id={FORGEJO_CLIENT_ID}" in location, f"client_id missing in OAuth location: {location}"
    return location


def get_or_create_pat():
    auth = base64.b64encode(f"{ADMIN_USER}:{ADMIN_PASSWORD}".encode()).decode()
    token_name = f"val-token-{int(time.time())}"
    token_payload = {
        "name": token_name,
        "scopes": ["all"]
    }
    req = urllib.request.Request(
        f"{FORGEJO_BASE_URL}/api/v1/users/{ADMIN_USER}/tokens",
        data=json.dumps(token_payload).encode(),
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data.get("sha1")


def test_forgejo_users_api(token):
    headers = {"Authorization": f"token {token}"}
    url = f"{FORGEJO_BASE_URL}/api/v1/admin/users"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        assert resp.status == 200, f"Expected HTTP 200 for admin users list, got {resp.status}"
        users_list = json.loads(resp.read().decode("utf-8"))
        return {u["username"]: u for u in users_list}


def test_organizations_and_repos(token):
    headers = {"Authorization": f"token {token}"}

    # Verify Orgs
    for org in EXPECTED_ORGS:
        url = f"{FORGEJO_BASE_URL}/api/v1/orgs/{org}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            assert resp.status == 200, f"Org {org} returned {resp.status}"

    # Verify Repos
    for repo_full in EXPECTED_REPOS:
        url = f"{FORGEJO_BASE_URL}/api/v1/repos/{repo_full}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            assert resp.status == 200, f"Repo {repo_full} returned {resp.status}"
            repo_data = json.loads(resp.read().decode("utf-8"))
            assert repo_data.get("full_name") == repo_full, f"Repo name mismatch: {repo_data.get('full_name')}"


def test_git_smart_http_protocol(token):
    headers = {"Authorization": f"token {token}"}
    url = f"{FORGEJO_BASE_URL}/acme/storefront-app.git/info/refs?service=git-upload-pack"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        assert resp.status == 200, f"Smart HTTP returned status {resp.status}"
        ctype = resp.headers.get("Content-Type")
        assert "application/x-git-upload-pack-advertisement" in ctype, f"Invalid Git content-type: {ctype}"
        return ctype


def test_webhook_configuration(token):
    headers = {"Authorization": f"token {token}"}
    url = f"{FORGEJO_BASE_URL}/api/v1/repos/darueira-corp/platform-core/hooks"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        hooks = json.loads(resp.read().decode("utf-8"))
        assert len(hooks) > 0, "No hooks configured on platform-core"
        tekton_hook = [h for h in hooks if "webhook-listener" in h.get("config", {}).get("url", "")]
        assert len(tekton_hook) > 0, "Tekton webhook listener not found in repo hooks"
        return tekton_hook[0].get("config", {}).get("url")


POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "central-postgres.drr-corpshared-plat.svc.cluster.local")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.environ.get("POSTGRES_DB", "drr_git_db")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "drr_admin")
POSTGRES_PASS = os.environ.get("POSTGRES_PASS", "change-me-in-openbao")


def test_external_login_user_mappings():
    import psycopg
    conn = psycopg.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASS
    )
    with conn.cursor() as cur:
        cur.execute("SELECT u.name, e.external_id, e.provider, e.email FROM external_login_user e JOIN \"user\" u ON e.user_id = u.id;")
        rows = cur.fetchall()
        mapped_users = {r[0]: {"external_id": r[1], "provider": r[2], "email": r[3]} for r in rows}
    conn.close()

    for user in TEST_USERS:
        u_name = user["username"]
        assert u_name in mapped_users, f"User {u_name} is not linked in external_login_user table"
        m = mapped_users[u_name]
        assert m["provider"] == "openidConnect", f"Invalid provider for {u_name}: {m['provider']}"
        assert m["external_id"], f"Missing external_id for {u_name}"
    return mapped_users


def main():
    print("==================================================================")
    print("  Phase 04: Forgejo Git Server Keycloak OIDC IAM Validation Suite ")
    print("==================================================================")

    # 1. Keycloak OIDC Client Registration
    print("\n[1/7] Validating Keycloak Central OIDC Client ('forgejo-git')...")
    client_info = test_keycloak_oidc_client()
    print(f"      [✓] Keycloak Client active: {client_info.get('clientId')} (Protocol: {client_info.get('protocol')})")

    # 2. Keycloak Direct Token Grant & UserInfo Assertions
    print("\n[2/7] Validating Keycloak OIDC Authentication & Custom Claims (tenant, email)...")
    for user in TEST_USERS:
        u_name = user["username"]
        ui = test_user_oidc_authentication(user)
        print(f"      [✓] User '{u_name}': Tenant={ui.get('tenant')}, Email={ui.get('email')}")

    # 3. Forgejo OAuth2 Login Redirect Endpoint
    print("\n[3/7] Validating Forgejo Git OAuth2 Authorization Redirect Flow...")
    loc = test_forgejo_oauth_redirect()
    print(f"      [✓] Direct OAuth2 entrypoint redirected cleanly to Keycloak IdP")

    # 4. External Login User Mappings in DB
    print("\n[4/7] Validating Pre-Linked Keycloak OIDC External User Mappings in Database...")
    mappings = test_external_login_user_mappings()
    for u_name, data in mappings.items():
        print(f"      [✓] User '{u_name}' mapped to Keycloak Sub: {data['external_id']}")

    # Generate token for API tests
    token = get_or_create_pat()

    # 5. Forgejo REST API Authentication
    print("\n[5/7] Validating Forgejo REST API User Profiles & Privileges...")
    user_map = test_forgejo_users_api(token)
    for user in TEST_USERS:
        u_name = user["username"]
        assert u_name in user_map, f"User {u_name} not found in Forgejo"
        profile = user_map[u_name]
        assert profile.get("email") == user["email"], f"Email mismatch for {u_name}: {profile.get('email')}"
        if user["expected_admin"]:
            assert profile.get("is_admin") is True, f"User {u_name} was expected to be an admin"
        exp_admin = "Administrator" if user["expected_admin"] else "Standard User"
        print(f"      [✓] Profile verified: {u_name} ({exp_admin}, Admin={profile.get('is_admin')})")

    # 6. Multi-Tenant Organizations & Repositories
    print("\n[6/7] Validating Multi-Tenant Organizations & Starter Repositories...")
    test_organizations_and_repos(token)
    print(f"      [✓] All {len(EXPECTED_ORGS)} organizations verified: {EXPECTED_ORGS}")
    print(f"      [✓] All {len(EXPECTED_REPOS)} repositories verified: {EXPECTED_REPOS}")

    # 7. Git Smart HTTP & Tekton CI Webhook
    print("\n[7/7] Validating Git Smart HTTP & Tekton CI Webhook Integration...")
    ctype = test_git_smart_http_protocol(token)
    print(f"      [✓] Git upload-pack advertisement verified ({ctype})")
    hook_url = test_webhook_configuration(token)
    print(f"      [✓] Tekton EventListener Webhook active: {hook_url}")

    print("\n==================================================================")
    print("  [✓✓✓] ALL PHASE 04 FORGEJO KEYCLOAK OIDC VALIDATION TESTS PASSED")
    print("==================================================================")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[✗] Validation failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
