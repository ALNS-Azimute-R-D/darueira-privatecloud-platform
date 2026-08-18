#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Enterprise Shared Services
Declarative Forgejo Git Keycloak OIDC IAM & Repository Bootstrapper
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
import psycopg

FORGEJO_HOST = os.environ.get("FORGEJO_HOST", "forgejo-git.drr-corpshared-plat.svc.cluster.local:3000")
FORGEJO_BASE_URL = f"http://{FORGEJO_HOST}"
ADMIN_USER = "drradmin"
ADMIN_PASSWORD = os.environ.get("FORGEJO_ADMIN_PASSWORD", "darueira-admin123")
TEKTON_WEBHOOK_URL = os.environ.get("TEKTON_WEBHOOK_URL", "http://el-forgejo-webhook-listener.drr-corpshared-mgmt.svc.cluster.local:8080")

POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "central-postgres.drr-corpshared-plat.svc.cluster.local")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.environ.get("POSTGRES_DB", "drr_git_db")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "drr_admin")
POSTGRES_PASS = os.environ.get("POSTGRES_PASS", "change-me-in-openbao")

KEYCLOAK_BASE_URL = os.environ.get("KEYCLOAK_BASE_URL", "http://keycloak.drr-corpshared-plat.svc.cluster.local:8080")
KEYCLOAK_ADMIN_USER = os.environ.get("KEYCLOAK_ADMIN_USER", "admin")
KEYCLOAK_ADMIN_PASS = os.environ.get("KEYCLOAK_ADMIN_PASS", "admin123-dev")
REALM_NAME = "darueira-platform-svcs"

FORGEJO_CLIENT_ID = "forgejo-git"
FORGEJO_CLIENT_SECRET = "darueira-forgejo-secret-2026"
FORGEJO_AUTH_SOURCE_NAME = "keycloak-oidc"

USERS = [
    ("andre.nascimento", "andre.nascimento@darueira.local", "Darueira@2026!", True, "darueira-corp"),
    ("alice.developer", "alice.developer@darueira.local", "Darueira@2026!", False, "acme"),
    ("bob.engineer", "bob.engineer@darueira.local", "Darueira@2026!", False, "acme"),
    ("carol.contractor", "carol.contractor@globex.local", "Darueira@2026!", False, "globex")
]

ORGANIZATIONS = ["darueira-corp", "acme", "globex"]

REPOSITORIES = [
    ("darueira-corp", "platform-core", "Core platform Helm charts and manifest repository"),
    ("acme", "storefront-app", "Acme e-Commerce Storefront microfrontend repository"),
    ("acme", "logistics-svc", "Acme Logistics & Order Processing service repository"),
    ("globex", "security-audit", "Globex security compliance and audit repository")
]


class KeycloakClient:
    def __init__(self, base_url, user, password):
        self.base_url = base_url.rstrip("/")
        self.token = self._get_token(user, password)

    def _get_token(self, user, password):
        url = f"{self.base_url}/realms/master/protocol/openid-connect/token"
        data = urllib.parse.urlencode({
            "client_id": "admin-cli",
            "username": user,
            "password": password,
            "grant_type": "password"
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))["access_token"]

    def request(self, path, method="GET", data=None):
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        body = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 204 or resp.length == 0:
                    return None
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 409:
                return None
            raise


def bootstrap_keycloak_client():
    print(f"--> Bootstrapping Keycloak OIDC Client '{FORGEJO_CLIENT_ID}' in Realm '{REALM_NAME}'...")
    kc = KeycloakClient(KEYCLOAK_BASE_URL, KEYCLOAK_ADMIN_USER, KEYCLOAK_ADMIN_PASS)
    clients = kc.request(f"admin/realms/{REALM_NAME}/clients?clientId={FORGEJO_CLIENT_ID}") or []

    payload = {
        "clientId": FORGEJO_CLIENT_ID,
        "name": "Forgejo Git Server",
        "description": "Internal Git Repository Manager with Keycloak OIDC Authentication",
        "protocol": "openid-connect",
        "enabled": True,
        "publicClient": False,
        "clientAuthenticatorType": "client-secret",
        "secret": FORGEJO_CLIENT_SECRET,
        "standardFlowEnabled": True,
        "directAccessGrantsEnabled": True,
        "serviceAccountsEnabled": True,
        "fullScopeAllowed": True,
        "redirectUris": [
            "https://git.darueira-corpshared.127.0.0.1.nip.io/*",
            "https://git.darueira-corpshared.127.0.0.1.nip.io:9443/*",
            "http://git.darueira-corpshared.127.0.0.1.nip.io:9080/*",
            "https://git.darueira-corpshared.127.0.0.1.nip.io/user/oauth2/keycloak-oidc/callback",
            "https://git.darueira-corpshared.127.0.0.1.nip.io:9443/user/oauth2/keycloak-oidc/callback",
            "http://git.darueira-corpshared.127.0.0.1.nip.io:9080/user/oauth2/keycloak-oidc/callback",
            "http://localhost:*/*",
            "*"
        ],
        "webOrigins": ["*"],
        "protocolMappers": [
            {
                "name": "email-claim",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-attribute-mapper",
                "consentRequired": False,
                "config": {
                    "user.attribute": "email",
                    "claim.name": "email",
                    "jsonType.label": "String",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true"
                }
            },
            {
                "name": "groups-claim",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-group-membership-mapper",
                "consentRequired": False,
                "config": {
                    "claim.name": "groups",
                    "full.path": "false",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true"
                }
            },
            {
                "name": "tenant-claim",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-attribute-mapper",
                "consentRequired": False,
                "config": {
                    "user.attribute": "tenant",
                    "claim.name": "tenant",
                    "jsonType.label": "String",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true"
                }
            }
        ]
    }

    if not clients:
        kc.request(f"admin/realms/{REALM_NAME}/clients", method="POST", data=payload)
        print(f"    [✓] Created Keycloak OIDC Client: {FORGEJO_CLIENT_ID}")
    else:
        client_id = clients[0]["id"]
        payload["id"] = client_id
        kc.request(f"admin/realms/{REALM_NAME}/clients/{client_id}", method="PUT", data=payload)
        print(f"    [✓] Updated Keycloak OIDC Client: {FORGEJO_CLIENT_ID}")


def bootstrap_forgejo_oauth_in_db():
    print(f"--> Ensuring Forgejo OAuth2 Provider '{FORGEJO_AUTH_SOURCE_NAME}' in PostgreSQL...")
    conn = psycopg.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASS
    )

    cfg_dict = {
        "Provider": "openidConnect",
        "ClientID": FORGEJO_CLIENT_ID,
        "ClientSecret": FORGEJO_CLIENT_SECRET,
        "OpenIDConnectAutoDiscoveryURL": f"{KEYCLOAK_BASE_URL}/realms/{REALM_NAME}/.well-known/openid-configuration",
        "CustomURLMapping": {
            "AuthURL": f"https://keycloak.darueira-corpshared.127.0.0.1.nip.io/realms/{REALM_NAME}/protocol/openid-connect/auth",
            "TokenURL": f"{KEYCLOAK_BASE_URL}/realms/{REALM_NAME}/protocol/openid-connect/token",
            "ProfileURL": f"{KEYCLOAK_BASE_URL}/realms/{REALM_NAME}/protocol/openid-connect/userinfo"
        },
        "IconURL": "",
        "Scopes": None,
        "RequiredClaimName": "",
        "RequiredClaimValue": "",
        "GroupClaimName": "groups",
        "AdminGroup": "drr-platform-admins",
        "GroupTeamMap": "",
        "GroupTeamMapRemoval": False,
        "RestrictedGroup": ""
    }
    cfg_json = json.dumps(cfg_dict)

    with conn.cursor() as cur:
        cur.execute("SELECT id FROM login_source WHERE name = %s;", (FORGEJO_AUTH_SOURCE_NAME,))
        row = cur.fetchone()
        if row:
            source_id = row[0]
            cur.execute("UPDATE login_source SET type = 6, is_active = true, cfg = %s WHERE id = %s;", (cfg_json, source_id))
            print(f"    [✓] Updated Keycloak OIDC source (ID: {source_id})")
        else:
            cur.execute(
                "INSERT INTO login_source (type, name, is_active, is_sync_enabled, cfg, created_unix, updated_unix) VALUES (6, %s, true, false, %s, %s, %s) RETURNING id;",
                (FORGEJO_AUTH_SOURCE_NAME, cfg_json, int(time.time()), int(time.time()))
            )
            source_id = cur.fetchone()[0]
            print(f"    [✓] Created Keycloak OIDC source (ID: {source_id})")

        # Migrate any LDAP users to Keycloak OIDC source & delete LDAP source
        cur.execute("UPDATE \"user\" SET login_type = 6, login_source = %s WHERE login_source IN (SELECT id FROM login_source WHERE type = 2);", (source_id,))
        cur.execute("DELETE FROM login_source WHERE type = 2;")
        conn.commit()

    conn.close()
    return source_id


def ensure_users_via_api(source_id):
    print("--> Ensuring Corporate Users & Privileges in Forgejo via REST API...")
    auth = base64.b64encode(f"{ADMIN_USER}:{ADMIN_PASSWORD}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}

    req_users = urllib.request.Request(f"{FORGEJO_BASE_URL}/api/v1/admin/users", headers=headers)
    existing_users = {}
    try:
        with urllib.request.urlopen(req_users, timeout=10) as resp:
            users_list = json.loads(resp.read().decode())
            existing_users = {u["username"]: u for u in users_list}
    except Exception as e:
        print(f"    Warning listing users: {e}")

    for username, email, password, is_admin, _ in USERS:
        if username not in existing_users:
            payload = {
                "username": username,
                "email": email,
                "password": password,
                "must_change_password": False,
                "login_name": username,
                "source_id": source_id
            }
            req_create = urllib.request.Request(
                f"{FORGEJO_BASE_URL}/api/v1/admin/users",
                data=json.dumps(payload).encode(),
                headers=headers,
                method="POST"
            )
            try:
                with urllib.request.urlopen(req_create, timeout=10) as resp:
                    print(f"    [✓] Created User: {username}")
            except urllib.error.HTTPError as e:
                print(f"    Create user {username} note: {e.code}")

        if is_admin:
            patch_payload = {"admin": True}
            req_patch = urllib.request.Request(
                f"{FORGEJO_BASE_URL}/api/v1/admin/users/{username}",
                data=json.dumps(patch_payload).encode(),
                headers=headers,
                method="PATCH"
            )
            try:
                with urllib.request.urlopen(req_patch, timeout=10) as resp:
                    print(f"    [✓] Granted Admin privileges to: {username}")
            except Exception as e:
                print(f"    Grant admin note: {e}")

        print(f"    [✓] User ready: {username:20} (Admin: {is_admin})")


def configure_orgs_and_repos():
    print("--> Provisioning Corporate Organizations, Teams & Repositories...")
    auth = base64.b64encode(f"{ADMIN_USER}:{ADMIN_PASSWORD}".encode()).decode()
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
            with urllib.request.urlopen(req, timeout=10) as resp:
                print(f"    [✓] Created Organization: {org}")
        except urllib.error.HTTPError as e:
            if e.code in (400, 409, 422):
                print(f"    [✓] Organization {org} already exists.")
            else:
                print(f"    Org {org} note: HTTP {e.code}")

    # 2. Add Users to Org Teams
    for username, _, _, _, org in USERS:
        try:
            req_teams = urllib.request.Request(f"{FORGEJO_BASE_URL}/api/v1/orgs/{org}/teams", headers=headers)
            with urllib.request.urlopen(req_teams, timeout=10) as resp:
                teams = json.loads(resp.read().decode())
                for t in teams:
                    team_id = t["id"]
                    req_add = urllib.request.Request(
                        f"{FORGEJO_BASE_URL}/api/v1/teams/{team_id}/members/{username}",
                        headers=headers,
                        method="PUT"
                    )
                    try:
                        urllib.request.urlopen(req_add, timeout=10)
                        print(f"    [✓] Added {username} to org '{org}' (Team: {t['name']})")
                    except Exception:
                        pass
        except Exception as e:
            print(f"    Team assignment note for {username}: {e}")

    # 3. Create Repositories
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
            with urllib.request.urlopen(req, timeout=10) as resp:
                print(f"    [✓] Created Repository: {org}/{repo_name}")
        except urllib.error.HTTPError as e:
            if e.code in (400, 409, 422):
                print(f"    [✓] Repository {org}/{repo_name} already exists.")
            else:
                print(f"    Repo {org}/{repo_name} note: HTTP {e.code}")

    # 4. Configure Tekton Webhook on platform-core
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
        with urllib.request.urlopen(hook_req, timeout=10) as resp:
            print("    [✓] Configured Tekton CI Webhook for darueira-corp/platform-core")
    except urllib.error.HTTPError as e:
        if e.code in (400, 409, 422):
            print("    [✓] Tekton CI Webhook already configured.")
        else:
            print(f"    Webhook note: HTTP {e.code}")


def main():
    print("==================================================================")
    print("  Bootstrapping Forgejo Git Server & Keycloak Central OIDC IAM    ")
    print("==================================================================")

    # 1. Health check
    for _ in range(10):
        try:
            with urllib.request.urlopen(f"{FORGEJO_BASE_URL}/api/v1/version", timeout=3) as resp:
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(2)

    # 2. Keycloak OIDC Client Registration
    bootstrap_keycloak_client()

    # 3. Forgejo OAuth2 Configuration in PostgreSQL
    source_id = bootstrap_forgejo_oauth_in_db()

    # 4. User Provisioning & Permissions
    ensure_users_via_api(source_id)

    # 5. Organizations, Teams & Repositories
    configure_orgs_and_repos()

    print("\n[✓] Forgejo Git Server Keycloak OIDC IAM bootstrap completed successfully!")


if __name__ == "__main__":
    main()
