#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Zero Trust In-Pod Interception Sidecars
Envoy PEP & OPA PDP Sidecar Interception Validation Suite
==============================================================================
"""

import sys
import os
import json
import urllib.request
import urllib.parse
import urllib.error

ENVOY_BASE_URL = os.environ.get("ENVOY_BASE_URL", "http://acme-storefront-app.drr-tnt-acme.svc.cluster.local:8000")


def send_request(path, headers=None, method="GET"):
    headers = headers or {}
    url = f"{ENVOY_BASE_URL.rstrip('/')}{path}"
    req = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, body, dict(resp.headers)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return e.code, body, dict(e.headers)


def main():
    print("==================================================================")
    print("  Phase 08: Envoy PEP & OPA PDP Sidecar Validation Suite          ")
    print("==================================================================")

    # 1. Healthcheck Bypass
    print("\n[1/7] Validating Ingress Interception & Public Healthcheck Bypass...")
    status, body, _ = send_request("/healthz")
    assert status == 200, f"Expected HTTP 200 from /healthz, got {status}"
    assert "acme-storefront-app" in body, f"Unexpected body from /healthz: {body}"
    print("      [✓] Public health check endpoint (/healthz) bypassed auth successfully (HTTP 200 OK)")

    # 2. Metrics Bypass
    print("\n[2/7] Validating Ingress Interception & Public Prometheus Metrics Bypass...")
    status, body, _ = send_request("/metrics")
    assert status == 200, f"Expected HTTP 200 from /metrics, got {status}"
    assert "acme_orders_total" in body, f"Unexpected metrics body: {body}"
    print("      [✓] Public Prometheus metrics endpoint (/metrics) bypassed auth successfully (HTTP 200 OK)")

    # 3. Anonymous Access to Protected Route
    print("\n[3/7] Validating Fail-Closed Interception on Anonymous Protected Requests...")
    status, body, headers = send_request("/api/v1/orders")
    assert status == 403, f"Expected HTTP 403 Forbidden for anonymous access, got {status}"
    print("      [✓] Anonymous request to /api/v1/orders blocked immediately by Envoy PEP (HTTP 403 Forbidden)")

    # 4. Platform Administrator Access
    print("\n[4/7] Validating Platform Administrator Access Enforcement...")
    status, body, _ = send_request("/api/v1/orders", headers={"x-user-id": "admin-root"})
    assert status == 200, f"Expected HTTP 200 for admin user, got {status}"
    assert "ord-101" in body, f"Unexpected admin orders response: {body}"
    print("      [✓] Platform Administrator (admin-root) granted access to protected orders API (HTTP 200 OK)")

    # 5. SPIFFE Workload mTLS Identity Access
    print("\n[5/7] Validating SPIFFE Workload Identity Authorization...")
    spiffe_id = "spiffe://darueira.local/ns/drr-corpshared-plat/sa/drr-tenant-svc"
    status, body, _ = send_request("/api/v1/orders", headers={"x-spiffe-principal": spiffe_id})
    assert status == 200, f"Expected HTTP 200 for SPIFFE principal, got {status}"
    assert "ord-101" in body, f"Unexpected SPIFFE workload orders response: {body}"
    print(f"      [✓] SPIFFE workload principal '{spiffe_id}' authorized successfully (HTTP 200 OK)")

    # 6. Fine-Grained OpenFGA ReBAC Authorized Tenant Access (Alice in ACME)
    print("\n[6/7] Validating Fine-Grained OpenFGA ReBAC Tenant Authorization (Alice in ACME)...")
    alice_headers = {
        "x-user-id": "alice.developer",
        "x-tenant-id": "acme",
        "x-environment-id": "acme-storefront-prod"
    }
    status, body, _ = send_request("/api/v1/orders", headers=alice_headers)
    assert status == 200, f"Expected HTTP 200 for authorized developer Alice, got {status}"
    assert "acme" in body and "ord-101" in body, f"Unexpected Alice orders response: {body}"
    print("      [✓] Alice Developer granted access via OpenFGA ReBAC 'can_read' relation (HTTP 200 OK)")

    # 7. Fine-Grained OpenFGA ReBAC Cross-Tenant Deny (Carol in Globex)
    print("\n[7/7] Validating Zero Trust Cross-Tenant Isolation Enforcement (Carol in Globex)...")
    carol_headers = {
        "x-user-id": "carol.contractor",
        "x-tenant-id": "acme",
        "x-environment-id": "acme-storefront-prod"
    }
    status, body, _ = send_request("/api/v1/orders", headers=carol_headers)
    assert status == 403, f"Expected HTTP 403 Forbidden for cross-tenant access, got {status}"
    print("      [✓] Carol Contractor (Globex) strictly blocked from ACME environment (HTTP 403 Forbidden)")

    print("\n==================================================================")
    print("  [✓✓✓] ALL PHASE 08 ENVOY PEP & OPA PDP VALIDATION TESTS PASSED! ")
    print("==================================================================")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[✗] Validation failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
