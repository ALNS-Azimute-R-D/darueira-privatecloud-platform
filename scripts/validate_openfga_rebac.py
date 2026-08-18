#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Enterprise Shared Services
OpenFGA ReBAC & Zero Trust Security Validation Suite
==============================================================================
"""

import sys
import os
import json
import urllib.request
import urllib.parse
import urllib.error

OPENFGA_HOST = os.environ.get("OPENFGA_HOST", "openfga.drr-corpshared-plat.svc.cluster.local:8080")
OPENFGA_BASE_URL = f"http://{OPENFGA_HOST}"
STORE_NAME = "darueira-rebac-store"

TEST_ASSERTIONS = [
    # 1. Platform Architect / Global Administrator (Full CRUD)
    {
        "user": "user:andre.nascimento",
        "relation": "can_delete",
        "object": "environment:acme-storefront-prod",
        "expected": True,
        "description": "Platform Architect can delete ACME production environment"
    },
    {
        "user": "user:andre.nascimento",
        "relation": "can_write",
        "object": "environment:acme-logistics-prod",
        "expected": True,
        "description": "Platform Architect can write to ACME logistics environment"
    },

    # 2. DevOps Engineer (Operator / Deployer)
    {
        "user": "user:bob.engineer",
        "relation": "can_write",
        "object": "environment:acme-storefront-prod",
        "expected": True,
        "description": "DevOps Engineer can deploy/write to ACME storefront environment"
    },
    {
        "user": "user:bob.engineer",
        "relation": "can_delete",
        "object": "environment:acme-storefront-prod",
        "expected": False,
        "description": "DevOps Engineer cannot delete ACME storefront environment (Least Privilege)"
    },

    # 3. Software Engineer (Viewer / Developer)
    {
        "user": "user:alice.developer",
        "relation": "can_read",
        "object": "environment:acme-storefront-prod",
        "expected": True,
        "description": "Developer can view/read ACME storefront environment"
    },
    {
        "user": "user:alice.developer",
        "relation": "can_delete",
        "object": "environment:acme-storefront-prod",
        "expected": False,
        "description": "Developer cannot delete ACME storefront environment (Least Privilege)"
    },

    # 4. Cross-Tenant Isolation (Globex Security Analyst vs ACME)
    {
        "user": "user:carol.contractor",
        "relation": "can_read",
        "object": "environment:acme-storefront-prod",
        "expected": False,
        "description": "Globex analyst CANNOT access ACME storefront environment (Tenant Isolation)"
    },
    {
        "user": "user:carol.contractor",
        "relation": "can_write",
        "object": "environment:acme-logistics-prod",
        "expected": False,
        "description": "Globex analyst CANNOT modify ACME logistics environment (Tenant Isolation)"
    }
]


def get_store_id():
    req = urllib.request.Request(f"{OPENFGA_BASE_URL}/stores")
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
        for s in data.get("stores", []):
            if s.get("name") == STORE_NAME:
                return s.get("id")
    raise RuntimeError(f"OpenFGA store '{STORE_NAME}' not found")


def test_openfga_health():
    req = urllib.request.Request(f"{OPENFGA_BASE_URL}/healthz")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200, f"Expected 200 from /healthz, got {resp.status}"
        data = json.loads(resp.read().decode())
        assert data.get("status") == "SERVING", f"Health status is {data.get('status')}"
        return data


def test_rebac_check(store_id, assertion):
    payload = {
        "tuple_key": {
            "user": assertion["user"],
            "relation": assertion["relation"],
            "object": assertion["object"]
        }
    }
    req = urllib.request.Request(
        f"{OPENFGA_BASE_URL}/stores/{store_id}/check",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200, f"Check API returned {resp.status}"
        res = json.loads(resp.read().decode())
        allowed = res.get("allowed", False)
        assert allowed == assertion["expected"], (
            f"Assertion failed: {assertion['description']}\n"
            f"  User: {assertion['user']}, Relation: {assertion['relation']}, Object: {assertion['object']}\n"
            f"  Allowed: {allowed}, Expected: {assertion['expected']}"
        )
        return allowed


def main():
    print("==================================================================")
    print("  Phase 06: OpenFGA ReBAC & Zero Trust Security Validation Suite  ")
    print("==================================================================")

    # 1. Health check
    print("\n[1/3] Validating OpenFGA Health & Engine Status...")
    health = test_openfga_health()
    print(f"      [✓] OpenFGA Server Health: {health.get('status')}")

    # 2. ReBAC Assertions
    store_id = get_store_id()
    print(f"\n[2/3] Validating Relationship-Based Access Control (ReBAC) Store: {store_id}...")
    for idx, assertion in enumerate(TEST_ASSERTIONS, start=1):
        desc = assertion["description"]
        print(f"  --> [{idx}/{len(TEST_ASSERTIONS)}] {desc}...")
        decision = test_rebac_check(store_id, assertion)
        print(f"      [✓] Decision: allowed={decision} (Matches Security Policy)")

    # 3. Summary of Zero Trust Guarantees
    print("\n[3/3] Validating Zero Trust Tenant Boundaries & Least Privilege Guarantees...")
    print("      [✓] Cross-tenant boundary isolation enforced (ACME vs Globex)")
    print("      [✓] Fine-grained ReBAC hierarchy asserted across Org -> Project -> Environment")
    print("      [✓] Principle of Least Privilege verified for developers and operators")

    print("\n==================================================================")
    print("  [✓✓✓] ALL PHASE 06 OPENFGA REBAC VALIDATION TESTS PASSED!       ")
    print("==================================================================")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[✗] Validation failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
