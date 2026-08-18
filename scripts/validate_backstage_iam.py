#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Enterprise Shared Services
Spotify Backstage IDP & Keycloak OIDC Validation Suite
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

KEYCLOAK_BASE_URL = os.environ.get("KEYCLOAK_BASE_URL", "http://keycloak.drr-corpshared-plat.svc.cluster.local:8080")
BACKSTAGE_HOST = os.environ.get("BACKSTAGE_HOST", "backstage.drr-corpshared-mgmt.svc.cluster.local:7007")
BACKSTAGE_BASE_URL = f"http://{BACKSTAGE_HOST}"

REALM_NAME = "darueira-platform-svcs"
CLIENT_ID = "backstage-portal"
CLIENT_SECRET = "darueira-backstage-secret-2026"

TEST_USERS = [
    {
        "username": "andre.nascimento",
        "email": "andre.nascimento@darueira.local",
        "password": "Darueira@2026!",
        "expected_role": "role-platform-architect",
        "expected_tenant": "darueira"
    },
    {
        "username": "alice.developer",
        "email": "alice.developer@darueira.local",
        "password": "Darueira@2026!",
        "expected_role": "role-software-engineer",
        "expected_tenant": "acme"
    },
    {
        "username": "bob.engineer",
        "email": "bob.engineer@darueira.local",
        "password": "Darueira@2026!",
        "expected_role": "role-devops-engineer",
        "expected_tenant": "acme"
    },
    {
        "username": "carol.contractor",
        "email": "carol.contractor@globex.local",
        "password": "Darueira@2026!",
        "expected_role": "role-security-analyst",
        "expected_tenant": "globex"
    }
]

EXPECTED_COMPONENTS = [
    "apisix-gateway",
    "authentik-directory",
    "keycloak-central",
    "nexus-oss",
    "forgejo-git",
    "stalwart-mailserver",
    "argocd-gitops",
    "tekton-pipelines",
    "openfga-rebac"
]

EXPECTED_TEMPLATES = [
    "react-microfrontend-template",
    "spring-boot-kotlin-service",
    "go-microservice-template",
    "tenant-provisioning-template"
]


def test_keycloak_oidc_token(user_info):
    username = user_info["username"]
    password = user_info["password"]
    
    url = f"{KEYCLOAK_BASE_URL}/realms/{REALM_NAME}/protocol/openid-connect/token"
    data = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "password",
        "username": username,
        "password": password,
        "scope": "openid email profile"
    }).encode("utf-8")
    
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        assert resp.status == 200, f"Expected 200 for user {username}, got {resp.status}"
        token_res = json.loads(resp.read().decode("utf-8"))
        assert "access_token" in token_res, "Missing access_token"
        assert "id_token" in token_res, "Missing id_token"

        # Decode JWT payload (without verify just for claims assertion)
        id_token_parts = token_res["id_token"].split(".")
        padded = id_token_parts[1] + "=" * ((4 - len(id_token_parts[1]) % 4) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))

        assert claims.get("email") == user_info["email"], f"Email claim mismatch: {claims.get('email')}"
        assert user_info["expected_role"] in str(claims.get("groups", [])), f"Role claim {user_info['expected_role']} missing"
        return token_res, claims


def test_backstage_catalog_entities():
    url = f"{BACKSTAGE_BASE_URL}/api/catalog/entities"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as resp:
        assert resp.status == 200, f"Expected 200 from Backstage Catalog API, got {resp.status}"
        entities = json.loads(resp.read().decode("utf-8"))
        assert len(entities) >= 20, f"Expected at least 20 catalog entities, found {len(entities)}"

        entity_names = {e.get("metadata", {}).get("name") for e in entities}
        for comp in EXPECTED_COMPONENTS:
            assert comp in entity_names, f"Missing expected Component '{comp}' in catalog"
        
        for tmpl in EXPECTED_TEMPLATES:
            assert tmpl in entity_names, f"Missing expected Template '{tmpl}' in catalog"

        return entities


def test_backstage_scaffolder_templates():
    url = f"{BACKSTAGE_BASE_URL}/api/catalog/entities?filter=kind=template"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as resp:
        assert resp.status == 200, f"Expected 200 from Backstage Templates query, got {resp.status}"
        templates = json.loads(resp.read().decode("utf-8"))
        assert len(templates) == len(EXPECTED_TEMPLATES), f"Expected {len(EXPECTED_TEMPLATES)} templates, found {len(templates)}"
        return templates


def main():
    print("==================================================================")
    print("  Phase 05: Spotify Backstage IDP & Keycloak OIDC Validation Suite")
    print("==================================================================")

    # 1. Keycloak OIDC Token Exchange for Backstage
    print("\n[1/3] Validating Keycloak OIDC Direct Grant & Token Exchange for Backstage...")
    for user in TEST_USERS:
        u_name = user["username"]
        role = user["expected_role"]
        tenant = user["expected_tenant"]
        print(f"  --> Authenticating {u_name} (Role: {role}, Tenant: {tenant})...")
        _, claims = test_keycloak_oidc_token(user)
        print(f"      [✓] OIDC Token Issued: Subject={claims.get('sub')}, Email={claims.get('email')}")

    # 2. Backstage Catalog Entities Health
    print("\n[2/3] Validating Backstage Catalog Entities API & Multi-Tier Topology...")
    entities = test_backstage_catalog_entities()
    kinds = {}
    for e in entities:
        k = e.get("kind")
        kinds[k] = kinds.get(k, 0) + 1
    print(f"      [✓] Total {len(entities)} catalog entities loaded and active:")
    for k, v in sorted(kinds.items()):
        print(f"          - {k:15}: {v:2} active items")

    # 3. Scaffolder Software Templates
    print("\n[3/3] Validating Scaffolder Golden Path Software Templates...")
    templates = test_backstage_scaffolder_templates()
    print(f"      [✓] All {len(templates)} golden path software templates verified:")
    for t in templates:
        t_name = t.get("metadata", {}).get("name")
        t_title = t.get("metadata", {}).get("title", t_name)
        print(f"          - {t_name:25} -> {t_title}")

    print("\n==================================================================")
    print("  [✓✓✓] ALL PHASE 05 SPOTIFY BACKSTAGE IDP VALIDATION TESTS PASSED")
    print("==================================================================")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[✗] Validation failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
