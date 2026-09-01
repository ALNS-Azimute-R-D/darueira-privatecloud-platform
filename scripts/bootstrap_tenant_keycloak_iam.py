#!/usr/bin/env python3
"""
==============================================================================
Script: scripts/bootstrap_tenant_keycloak_iam.py
Purpose: Declarative, idempotent bootstrap of Tenant Keycloak (swfabrik-europe),
         OIDC Clients, Identity Provider Federation with Central Keycloak
         (darueira-platform-svcs), Role Mappers, and Test Personas.
==============================================================================
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error

TENANT_KEYCLOAK_BASE_URL = os.environ.get(
    "TENANT_KEYCLOAK_BASE_URL",
    "http://tenant-keycloak.drr-tnt-swfabrik-europe-dev.svc.cluster.local:8080"
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

REALM_NAME = "swfabrik-europe"
REALM_DISPLAY = "SWFabrik Europe Tenant"


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
            if e.code == 404:
                return None
            err_body = e.read().decode("utf-8") if e.fp else ""
            print(f"[ERROR] HTTP {e.code} on {method} {url}: {err_body}", file=sys.stderr)
            raise


def bootstrap_tenant():
    print("==================================================================")
    print("  Bootstrapping Tenant Keycloak IAM & Central SSO Identity Broker ")
    print("  Tenant Realm: swfabrik-europe                                  ")
    print("  Central Realm: darueira-platform-svcs                          ")
    print("==================================================================")

    kc = KeycloakAdminClient(TENANT_KEYCLOAK_BASE_URL, TENANT_KEYCLOAK_ADMIN_USER, TENANT_KEYCLOAK_ADMIN_PASS)

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

    desired_mappers = [
        {
            "name": "hardcode-role-food-market-admin",
            "identityProviderAlias": idp_alias,
            "identityProviderMapper": "oidc-hardcoded-role-idp-mapper",
            "config": {"role": "ROLE_FOOD_MARKET_ADMIN", "syncMode": "FORCE"}
        },
        {
            "name": "hardcode-role-food-market-manager",
            "identityProviderAlias": idp_alias,
            "identityProviderMapper": "oidc-hardcoded-role-idp-mapper",
            "config": {"role": "ROLE_FOOD_MARKET_MANAGER", "syncMode": "FORCE"}
        },
        {
            "name": "hardcode-role-food-market-user",
            "identityProviderAlias": idp_alias,
            "identityProviderMapper": "oidc-hardcoded-role-idp-mapper",
            "config": {"role": "ROLE_FOOD_MARKET_USER", "syncMode": "FORCE"}
        },
        {
            "name": "hardcode-role-legalhub-admin",
            "identityProviderAlias": idp_alias,
            "identityProviderMapper": "oidc-hardcoded-role-idp-mapper",
            "config": {"role": "ROLE_LEGALHUB_ADMIN", "syncMode": "FORCE"}
        },
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
