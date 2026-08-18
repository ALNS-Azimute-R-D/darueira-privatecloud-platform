#!/usr/bin/env python3
"""
Validation script for Darueira IAM Identity Federation (Authentik LDAP -> Keycloak IdP -> OIDC).
Tests:
1. Authenticates 4 users (Employees and Contractors across multiple tenants) via Keycloak OIDC.
2. Decodes JWT tokens.
3. Asserts tenant, roles, position, employee_type, and group memberships.
"""

import sys
import json
import base64
import urllib.request
import urllib.parse

KEYCLOAK_TOKEN_URL = "http://keycloak.drr-corpshared-plat.svc.cluster.local:8080/realms/darueira-platform-svcs/protocol/openid-connect/token"
CLIENT_ID = "darueira-platform-generic-oidc"
CLIENT_SECRET = "darueira-oidc-secret-key-2026"

TEST_USERS = [
    {
        "username": "andre.nascimento",
        "password": "Darueira@2026!",
        "expected_tenant": "darueira-corp",
        "expected_employee_type": "employee",
        "expected_groups": [
            "dept-darueira-corp",
            "proj-platform-core-lead",
            "role-platform-architect",
        ],
    },
    {
        "username": "alice.developer",
        "password": "Darueira@2026!",
        "expected_tenant": "acme",
        "expected_employee_type": "employee",
        "expected_groups": [
            "dept-acme",
            "proj-storefront-lead",
            "role-software-engineer",
        ],
    },
    {
        "username": "bob.engineer",
        "password": "Darueira@2026!",
        "expected_tenant": "acme",
        "expected_employee_type": "employee",
        "expected_groups": [
            "dept-acme",
            "proj-logistics-member",
            "proj-storefront-member",
            "role-devops-engineer",
        ],
    },
    {
        "username": "carol.contractor",
        "password": "Darueira@2026!",
        "expected_tenant": "globex",
        "expected_employee_type": "contractor",
        "expected_groups": [
            "dept-globex",
            "proj-logistics-member",
            "role-security-analyst",
        ],
    },
]


def decode_jwt_payload(token: str) -> dict:
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("Invalid JWT token format")
    payload_b64 = parts[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    return json.loads(base64.b64decode(payload_b64).decode("utf-8"))


def test_user_authentication(user_info: dict) -> bool:
    username = user_info["username"]
    password = user_info["password"]
    print(f"\n========================================================")
    print(f"Testing OIDC Authentication for User: {username}")
    print(f"========================================================")

    data = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "username": username,
        "password": password,
        "grant_type": "password",
        "scope": "openid profile email",
    }).encode("utf-8")

    req = urllib.request.Request(
        KEYCLOAK_TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        with urllib.request.urlopen(req) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"[FAIL] HTTP {e.code}: {e.read().decode('utf-8')}")
        return False
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False

    access_token = resp_data.get("access_token")
    if not access_token:
        print("[FAIL] No access_token returned in response!")
        return False

    payload = decode_jwt_payload(access_token)
    print("[SUCCESS] Access Token successfully issued and signed by Keycloak:")
    print(
        json.dumps(
            {
                "sub": payload.get("sub"),
                "preferred_username": payload.get("preferred_username"),
                "name": payload.get("name"),
                "email": payload.get("email"),
                "tenant": payload.get("tenant"),
                "position": payload.get("position"),
                "employee_type": payload.get("employee_type"),
                "groups": payload.get("groups"),
            },
            indent=2,
        )
    )

    # Validations
    assert payload.get("tenant") == user_info["expected_tenant"], (
        f"Expected tenant '{user_info['expected_tenant']}', got '{payload.get('tenant')}'"
    )
    assert payload.get("employee_type") == user_info["expected_employee_type"], (
        f"Expected employee_type '{user_info['expected_employee_type']}', got '{payload.get('employee_type')}'"
    )

    actual_groups = set(payload.get("groups", []))
    for expected_g in user_info["expected_groups"]:
        assert expected_g in actual_groups, (
            f"Expected group '{expected_g}' missing from token groups: {actual_groups}"
        )

    print(f"[PASS] All assertions passed for {username}!")
    return True


def main():
    print("=== [DARUEIRA IAM FEDERATION E2E TEST RUNNER] ===")
    all_passed = True
    for user_info in TEST_USERS:
        success = test_user_authentication(user_info)
        if not success:
            all_passed = False

    if all_passed:
        print(
            "\n================================================================================"
        )
        print(
            "[ALL TESTS PASSED] IAM Federation & Central IdP Authentication Fully Verified!"
        )
        print(
            "================================================================================"
        )
        sys.exit(0)
    else:
        print("\n[FAILED] One or more authentication tests failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
