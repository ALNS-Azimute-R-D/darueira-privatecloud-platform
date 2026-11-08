#!/usr/bin/env python3
"""
==============================================================================
Script: scripts/bootstrap_tenant_keycloak_iam.py
Purpose: Declarative, idempotent bootstrap of a Tenant Keycloak realm, Identity
         Provider Federation with Central Keycloak (darueira-platform-svcs) and
         Role Mappers. Works for any tenant: pick it with TENANT_NAME
         (default swfabrik-europe; also swfabrik-latam).

Usage:   TENANT_NAME=swfabrik-latam python3 scripts/bootstrap_tenant_keycloak_iam.py
         The tenant Keycloak is reached at
         http://tenant-keycloak.drr-tnt-<TENANT_NAME>-dev.svc.cluster.local:8080
         (override with TENANT_KEYCLOAK_BASE_URL, e.g. a kubectl port-forward: the tenant
         network policy only lets pods of the tenant itself reach it).
Roles:   Role mappers per tenant are listed in TENANT_ROLE_MAPPERS below, or set
         TENANT_ROLE_MAPPERS_JSON='["ROLE_X","ROLE_Y"]' to override them.
==============================================================================
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error

TENANT_NAME = os.environ.get("TENANT_NAME", "swfabrik-europe")

TENANT_KEYCLOAK_BASE_URL = os.environ.get(
    "TENANT_KEYCLOAK_BASE_URL",
    f"http://tenant-keycloak.drr-tnt-{TENANT_NAME}-dev.svc.cluster.local:8080"
)
TENANT_KEYCLOAK_ADMIN_USER = os.environ.get("TENANT_KEYCLOAK_ADMIN_USER", "admin")
TENANT_KEYCLOAK_ADMIN_PASS = os.environ.get("TENANT_KEYCLOAK_ADMIN_PASS", "admin123")

CENTRAL_KEYCLOAK_INTERNAL = os.environ.get(
    "CENTRAL_KEYCLOAK_INTERNAL",
    "http://keycloak.drr-corpshared-plat.svc.cluster.local:8080"
)
CENTRAL_KEYCLOAK_EXTERNAL = os.environ.get(
    "CENTRAL_KEYCLOAK_EXTERNAL",
    "https://keycloak.darueira-corpshared.127.0.0.1.nip.io"
)

REALM_NAME = os.environ.get("TENANT_REALM", TENANT_NAME)
REALM_DISPLAY = os.environ.get(
    "TENANT_REALM_DISPLAY",
    {"swfabrik-europe": "SWFabrik Europe Tenant", "swfabrik-latam": "SWFabrik Latam Tenant"}.get(
        TENANT_NAME, TENANT_NAME.replace("-", " ").title() + " Tenant"
    ),
)

# Roles granted to every user that arrives through the Central SSO, per tenant. The europe list is the
# one this script always had. The latam list is empty on purpose: its applications (app-identity-studio,
# checkout-service) have no role contract yet, so none is invented here. Set it in this table or with
# TENANT_ROLE_MAPPERS_JSON when it exists.
TENANT_ROLE_MAPPERS = {
    "swfabrik-europe": [
        "ROLE_FOOD_MARKET_ADMIN",
        "ROLE_FOOD_MARKET_MANAGER",
        "ROLE_FOOD_MARKET_USER",
        "ROLE_LEGALHUB_ADMIN",
    ],
    "swfabrik-latam": [],
}
ROLE_MAPPERS = (
    json.loads(os.environ["TENANT_ROLE_MAPPERS_JSON"])
    if os.environ.get("TENANT_ROLE_MAPPERS_JSON")
    else TENANT_ROLE_MAPPERS.get(TENANT_NAME, [])
)


class KeycloakAdminClient:
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
                status = resp.status
                if status in (204, 201) or resp.length == 0:
                    return None
                content = resp.read()
                return json.loads(content.decode("utf-8")) if content else None
        except urllib.error.HTTPError as e:
            # A missing resource is only an answer for a read. On a write it means the target does not exist
            # (for instance an absent realm) and must not look like success.
            if e.code == 404 and method == "GET":
                return None
            err_body = e.read().decode("utf-8") if e.fp else ""
            print(f"[ERROR] HTTP {e.code} on {method} {url}: {err_body}", file=sys.stderr)
            raise


def bootstrap_tenant():
    print("==================================================================")
    print("  Bootstrapping Tenant Keycloak IAM & Central SSO Identity Broker ")
    print(f"  Tenant Realm: {REALM_NAME}")
    print("  Central Realm: darueira-platform-svcs                          ")
    print("==================================================================")

    kc = KeycloakAdminClient(TENANT_KEYCLOAK_BASE_URL, TENANT_KEYCLOAK_ADMIN_USER, TENANT_KEYCLOAK_ADMIN_PASS)

    # 0. The tenant realm itself (a fresh tenant Keycloak only has `master`)
    print(f"--> 0. Ensuring Realm '{REALM_NAME}' exists...")
    if kc.request(f"admin/realms/{REALM_NAME}") is None:
        kc.request("admin/realms", method="POST", data={
            "realm": REALM_NAME,
            "displayName": REALM_DISPLAY,
            "enabled": True,
            "loginWithEmailAllowed": True,
            "registrationAllowed": False,
            "duplicateEmailsAllowed": False,
        })
        if kc.request(f"admin/realms/{REALM_NAME}") is None:
            raise RuntimeError(f"Realm '{REALM_NAME}' was not created")
        print(f"    [+] Created realm '{REALM_NAME}'")
    else:
        print(f"    [=] Realm '{REALM_NAME}' exists")

    # 1. Identity Provider Configuration (Central SSO)
    print("--> 1. Configuring Identity Provider 'darueira-central-keycloak'...")
    idp_alias = "darueira-central-keycloak"
    existing_idp = kc.request(f"admin/realms/{REALM_NAME}/identity-provider/instances/{idp_alias}")

    idp_payload = {
        "alias": idp_alias,
        "displayName": "Darueira Platform Central SSO",
        "providerId": "keycloak-oidc",
        "enabled": True,
        "trustEmail": True,
        "storeToken": True,
        "addReadTokenRoleOnCreate": True,
        "authenticateByDefault": False,
        "linkOnly": False,
        "hideOnLogin": False,
        "firstBrokerLoginFlowAlias": "first broker login",
        "config": {
            "authorizationUrl": f"{CENTRAL_KEYCLOAK_EXTERNAL}/realms/darueira-platform-svcs/protocol/openid-connect/auth",
            "authUrl": f"{CENTRAL_KEYCLOAK_EXTERNAL}/realms/darueira-platform-svcs/protocol/openid-connect/auth",
            "tokenUrl": f"{CENTRAL_KEYCLOAK_INTERNAL}/realms/darueira-platform-svcs/protocol/openid-connect/token",
            "userInfoUrl": f"{CENTRAL_KEYCLOAK_INTERNAL}/realms/darueira-platform-svcs/protocol/openid-connect/userinfo",
            "jwksUrl": f"{CENTRAL_KEYCLOAK_INTERNAL}/realms/darueira-platform-svcs/protocol/openid-connect/certs",
            "logoutUrl": f"{CENTRAL_KEYCLOAK_EXTERNAL}/realms/darueira-platform-svcs/protocol/openid-connect/logout",
            "issuer": f"{CENTRAL_KEYCLOAK_EXTERNAL}/realms/darueira-platform-svcs",
            "clientId": "darueira-platform-generic-oidc",
            "clientSecret": "darueira-oidc-secret-key-2026",
            "clientAuthMethod": "client_secret_post",
            "syncMode": "FORCE",
            "useJwksUrl": "true",
            "validateSignature": "true",
            "pkceEnabled": "false",
            "defaultScope": "openid profile email"
        }
    }

    if existing_idp:
        print("    Updating existing Identity Provider...")
        kc.request(f"admin/realms/{REALM_NAME}/identity-provider/instances/{idp_alias}", method="PUT", data=idp_payload)
    else:
        print("    Creating Identity Provider...")
        kc.request(f"admin/realms/{REALM_NAME}/identity-provider/instances", method="POST", data=idp_payload)
    print("    [✓] Identity Provider 'darueira-central-keycloak' configured!")

    # 2. Identity Provider Mappers
    print("--> 2. Configuring IDP Mappers for Central SSO...")
    existing_mappers = kc.request(f"admin/realms/{REALM_NAME}/identity-provider/instances/{idp_alias}/mappers") or []
    existing_map_names = {m["name"] for m in existing_mappers}

    # One hardcoded-role mapper per role of the tenant. Names stay `hardcode-role-<role without ROLE_>`
    # (ROLE_FOOD_MARKET_ADMIN -> hardcode-role-food-market-admin) so an already configured realm is not duplicated.
    role_mappers = [
        {
            "name": "hardcode-role-" + role.removeprefix("ROLE_").lower().replace("_", "-"),
            "identityProviderAlias": idp_alias,
            "identityProviderMapper": "oidc-hardcoded-role-idp-mapper",
            "config": {"role": role, "syncMode": "FORCE"}
        }
        for role in ROLE_MAPPERS
    ]

    desired_mappers = role_mappers + [
        {
            "name": "username-importer",
            "identityProviderAlias": idp_alias,
            "identityProviderMapper": "oidc-username-idp-mapper",
            "config": {"template": "${CLAIM.preferred_username}", "target": "LOCAL", "syncMode": "FORCE"}
        },
        {
            "name": "attribute-tenant",
            "identityProviderAlias": idp_alias,
            "identityProviderMapper": "oidc-user-attribute-idp-mapper",
            "config": {"claim": "tenant", "user.attribute": "organization", "syncMode": "FORCE"}
        }
    ]

    for m in desired_mappers:
        if m["name"] not in existing_map_names:
            kc.request(f"admin/realms/{REALM_NAME}/identity-provider/instances/{idp_alias}/mappers", method="POST", data=m)
            print(f"    [+] Created mapper: {m['name']}")
        else:
            print(f"    [=] Mapper exists: {m['name']}")

    # 3. First Broker Login Review Profile Config
    print("--> 3. Configuring First Broker Login Execution (skip redundant profile prompt)...")
    executions = kc.request(f"admin/realms/{REALM_NAME}/authentication/flows/first%20broker%20login/executions") or []
    review_exec = next((e for e in executions if e.get("providerId") == "idp-review-profile"), None)
    if review_exec and review_exec.get("authenticationConfig"):
        cfg_id = review_exec["authenticationConfig"]
        cfg = kc.request(f"admin/realms/{REALM_NAME}/authentication/config/{cfg_id}")
        if cfg:
            cfg["config"]["update.profile.on.first.login"] = "missing"
            kc.request(f"admin/realms/{REALM_NAME}/authentication/config/{cfg_id}", method="PUT", data=cfg)
            print("    [✓] Set update.profile.on.first.login = missing")

    print("\n" + "=" * 80)
    print("  [SUCCESS] Tenant Keycloak IAM & SSO Federation Bootstrap Completed!")
    print("=" * 80)


if __name__ == "__main__":
    bootstrap_tenant()
