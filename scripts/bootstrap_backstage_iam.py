#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Enterprise Shared Services
Spotify Backstage IDP & Keycloak OIDC Federation Bootstrapper
==============================================================================
"""

import sys
import os
import json
import urllib.request
import urllib.parse
import urllib.error
import time

KEYCLOAK_BASE_URL = os.environ.get("KEYCLOAK_BASE_URL", "http://keycloak.drr-corpshared-plat.svc.cluster.local:8080")
KEYCLOAK_ADMIN_USER = os.environ.get("KEYCLOAK_ADMIN_USER", "admin")
KEYCLOAK_ADMIN_PASS = os.environ.get("KEYCLOAK_ADMIN_PASS", "admin123-dev")
REALM_NAME = "darueira-platform-svcs"

BACKSTAGE_CLIENT_ID = "backstage-portal"
BACKSTAGE_CLIENT_SECRET = "darueira-backstage-secret-2026"
BACKSTAGE_REDIRECT_URIS = [
    "https://backstage.darueira-corpshared.127.0.0.1.nip.io/*",
    "https://backstage.darueira-corpshared.127.0.0.1.nip.io/api/auth/oidc/handler/frame",
    "http://localhost:7007/*",
    "http://localhost:3000/*"
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


def bootstrap_backstage_oidc():
    print(f"--> Bootstrapping Keycloak OIDC Client '{BACKSTAGE_CLIENT_ID}'...")
    kc = KeycloakClient(KEYCLOAK_BASE_URL, KEYCLOAK_ADMIN_USER, KEYCLOAK_ADMIN_PASS)

    clients = kc.request(f"admin/realms/{REALM_NAME}/clients?clientId={BACKSTAGE_CLIENT_ID}") or []
    client_payload = {
        "clientId": BACKSTAGE_CLIENT_ID,
        "name": "Spotify Backstage Developer Portal",
        "description": "Internal Developer Portal (IDP) with Keycloak OIDC Authentication",
        "protocol": "openid-connect",
        "enabled": True,
        "publicClient": False,
        "clientAuthenticatorType": "client-secret",
        "secret": BACKSTAGE_CLIENT_SECRET,
        "standardFlowEnabled": True,
        "directAccessGrantsEnabled": True,
        "serviceAccountsEnabled": True,
        "fullScopeAllowed": True,
        "redirectUris": BACKSTAGE_REDIRECT_URIS,
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
        kc.request(f"admin/realms/{REALM_NAME}/clients", method="POST", data=client_payload)
        print(f"    [✓] Created Keycloak OIDC Client: {BACKSTAGE_CLIENT_ID}")
    else:
        client_id = clients[0]["id"]
        client_payload["id"] = client_id
        kc.request(f"admin/realms/{REALM_NAME}/clients/{client_id}", method="PUT", data=client_payload)
        print(f"    [✓] Updated Keycloak OIDC Client: {BACKSTAGE_CLIENT_ID}")


def main():
    print("==================================================================")
    print("  Bootstrapping Spotify Backstage IDP & Keycloak OIDC Federation  ")
    print("==================================================================")

    bootstrap_backstage_oidc()
    print("\n[✓] Backstage IDP IAM bootstrap completed successfully!")


if __name__ == "__main__":
    main()
