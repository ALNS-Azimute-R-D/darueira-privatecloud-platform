#!/usr/bin/env python3
"""
==============================================================================
Script: scripts/bootstrap_bookanything_keycloak_clients.py
Purpose: Idempotent creation of the Keycloak clients the BookAnything backend needs in the
         tenant realm (default: swfabrik-europe):
           - web_app             confidential client (the backend's OAuth2 client registration)
           - swaggerui-test-app  public client with PKCE (Swagger UI "Authorize" button)
         The generated secret of web_app is printed to stdout ONLY as `CLIENT_SECRET=<value>` when the
         client is created or when --print-secret is given, so a caller can store it in OpenBao.

Usage:   TENANT_KEYCLOAK_BASE_URL=http://127.0.0.1:18080 python3 scripts/bootstrap_bookanything_keycloak_clients.py
         (a kubectl port-forward of svc/tenant-keycloak; the tenant network policy only admits the tenant itself)
==============================================================================
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get(
    "TENANT_KEYCLOAK_BASE_URL",
    "http://tenant-keycloak.drr-tnt-swfabrik-europe-dev.svc.cluster.local:8080",
).rstrip("/")
ADMIN_USER = os.environ.get("TENANT_KEYCLOAK_ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("TENANT_KEYCLOAK_ADMIN_PASS", "admin123")
REALM = os.environ.get("TENANT_REALM", "swfabrik-europe")
HOSTS = os.environ.get(
    "BOOKANYTHING_HOSTS",
    "http://localhost:8060,http://bookanything-api.swfabrik-europe.127.0.0.1.nip.io,"
    "http://bookanything.swfabrik-europe.127.0.0.1.nip.io,http://localhost:4200",
).split(",")


def call(path, method="GET", data=None, token=None, form=False):
    headers = {}
    body = None
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE}/{path.lstrip('/')}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None), resp.headers
    except urllib.error.HTTPError as e:
        if e.code == 404 and method == "GET":
            return 404, None, e.headers
        print(f"[ERROR] HTTP {e.code} on {method} {path}: {e.read().decode()[:300]}", file=sys.stderr)
        raise


def find_client(token, client_id):
    _, found, _ = call(f"admin/realms/{REALM}/clients?clientId={urllib.parse.quote(client_id)}", token=token)
    return found[0] if found else None


def ensure_client(token, payload):
    existing = find_client(token, payload["clientId"])
    if existing:
        call(f"admin/realms/{REALM}/clients/{existing['id']}", "PUT", {**existing, **payload}, token)
        print(f"[=] client {payload['clientId']} updated", file=sys.stderr)
        return existing["id"], False
    call(f"admin/realms/{REALM}/clients", "POST", payload, token)
    print(f"[+] client {payload['clientId']} created", file=sys.stderr)
    return find_client(token, payload["clientId"])["id"], True


def main():
    _, tok, _ = call(
        "realms/master/protocol/openid-connect/token",
        "POST",
        {"client_id": "admin-cli", "username": ADMIN_USER, "password": ADMIN_PASS, "grant_type": "password"},
        form=True,
    )
    token = tok["access_token"]
    if call(f"admin/realms/{REALM}", token=token)[0] == 404:
        raise SystemExit(f"Realm '{REALM}' does not exist; run bootstrap_tenant_keycloak_iam.py first")

    redirects = [f"{h.strip()}/*" for h in HOSTS if h.strip()]
    origins = [h.strip() for h in HOSTS if h.strip()]

    web_id, created = ensure_client(token, {
        "clientId": "web_app",
        "name": "BookAnything backend (OAuth2 client)",
        "enabled": True,
        "protocol": "openid-connect",
        "publicClient": False,
        "standardFlowEnabled": True,
        "directAccessGrantsEnabled": False,
        "serviceAccountsEnabled": False,
        "redirectUris": redirects,
        "webOrigins": origins,
    })
    ensure_client(token, {
        "clientId": "swaggerui-test-app",
        "name": "BookAnything Swagger UI",
        "enabled": True,
        "protocol": "openid-connect",
        "publicClient": True,
        "standardFlowEnabled": True,
        "directAccessGrantsEnabled": False,
        "redirectUris": redirects,
        "webOrigins": origins,
        "attributes": {"pkce.code.challenge.method": "S256"},
    })

    if created or "--print-secret" in sys.argv:
        _, sec, _ = call(f"admin/realms/{REALM}/clients/{web_id}/client-secret", token=token)
        print(f"CLIENT_SECRET={sec['value']}")


if __name__ == "__main__":
    main()
