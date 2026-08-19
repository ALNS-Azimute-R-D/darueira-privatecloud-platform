#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Enterprise Secrets & Workload Identity
SPIRE Workload Identity & OpenBao Dynamic Secrets Validation Suite
==============================================================================
"""

import sys
import os
import json
import base64
import time
import subprocess
import urllib.request
import urllib.parse
import urllib.error

OPENBAO_HOST = os.environ.get("OPENBAO_HOST", "openbao-master.drr-corpshared-secr-internal.svc.cluster.local:8200")
OPENBAO_ADDR = f"http://{OPENBAO_HOST}"
OPENBAO_TOKEN = os.environ.get("OPENBAO_TOKEN", "darueira-root-token")

SPIRE_POD = os.environ.get("SPIRE_POD", "deploy/spire-server-placeholder")
SPIRE_NS = os.environ.get("SPIRE_NS", "drr-corpshared-secr-internal")
TRUST_DOMAIN = "darueira.local"

EXPECTED_WORKLOADS = [
    f"spiffe://{TRUST_DOMAIN}/ns/drr-corpshared-plat/sa/drr-iam-authz-svc",
    f"spiffe://{TRUST_DOMAIN}/ns/drr-corpshared-plat/sa/drr-tenant-svc",
    f"spiffe://{TRUST_DOMAIN}/ns/drr-corpshared-mgmt/sa/drr-env-orchestrator-svc",
    f"spiffe://{TRUST_DOMAIN}/ns/drr-corpshared-mgmt/sa/drr-operator",
    f"spiffe://{TRUST_DOMAIN}/ns/drr-tnt-acme/sa/acme-storefront-app",
    f"spiffe://{TRUST_DOMAIN}/ns/drr-tnt-acme/sa/acme-logistics-svc",
    f"spiffe://{TRUST_DOMAIN}/ns/drr-tnt-globex/sa/globex-security-audit"
]


def openbao_request(path, data=None, method="GET", token=OPENBAO_TOKEN):
    clean_path = path.lstrip("/")
    url = f"{OPENBAO_ADDR}/v1/{clean_path}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    headers = {
        "X-Vault-Token": token,
        "Content-Type": "application/json"
    }
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as resp:
        if resp.status == 204 or resp.length == 0:
            return None
        return json.loads(resp.read().decode("utf-8"))


def test_spire_server_health():
    cmd = f"microk8s kubectl exec -n {SPIRE_NS} {SPIRE_POD} -- /opt/spire/bin/spire-server healthcheck"
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
    assert "Server is healthy" in res.stdout, f"SPIRE health check failed: {res.stdout}"

    bundle_cmd = f"microk8s kubectl exec -n {SPIRE_NS} {SPIRE_POD} -- /opt/spire/bin/spire-server bundle show -format spiffe"
    b_res = subprocess.run(bundle_cmd, shell=True, capture_output=True, text=True, check=True)
    bundle_data = json.loads(b_res.stdout)
    assert len(bundle_data.get("keys", [])) > 0, "No keys found in SPIRE trust bundle"
    return bundle_data


def test_spire_workload_entries():
    cmd = f"microk8s kubectl exec -n {SPIRE_NS} {SPIRE_POD} -- /opt/spire/bin/spire-server entry show -output json"
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
    data = json.loads(res.stdout)
    registered_ids = set()
    for e in data.get("entries", []):
        sp_obj = e.get("spiffe_id", {})
        if isinstance(sp_obj, dict):
            sp_id = f"spiffe://{sp_obj.get('trust_domain')}{sp_obj.get('path')}"
        else:
            sp_id = str(sp_obj)
        registered_ids.add(sp_id)

    for expected_id in EXPECTED_WORKLOADS:
        assert expected_id in registered_ids, f"Workload entry missing in SPIRE: {expected_id}"
    return registered_ids


def mint_jwt_svid(spiffe_id, audience="openbao"):
    cmd = f"microk8s kubectl exec -n {SPIRE_NS} {SPIRE_POD} -- /opt/spire/bin/spire-server jwt mint -spiffeID {spiffe_id} -audience {audience}"
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
    jwt_token = res.stdout.strip()
    assert jwt_token, f"Failed to mint JWT SVID for {spiffe_id}"
    return jwt_token


def parse_jwt_claims(jwt_token):
    payload_b64 = jwt_token.split(".")[1]
    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(padded.encode()).decode("utf-8"))


def test_openbao_pki_issue():
    res = openbao_request("pki_int/issue/darueira-workload-role", data={
        "common_name": "drr-iam-authz-svc.drr-corpshared-plat.svc.cluster.local",
        "alt_names": "drr-iam-authz-svc.darueira.local"
    }, method="POST")
    assert res and "data" in res, "Failed to issue dynamic certificate from OpenBao PKI"
    data = res["data"]
    assert data.get("certificate"), "No certificate in PKI issue response"
    assert data.get("issuing_ca"), "No issuing CA in PKI issue response"
    return data


def authenticate_spiffe_jwt_with_openbao(jwt_svid, role_name):
    payload = {
        "role": role_name,
        "jwt": jwt_svid
    }
    res = openbao_request("auth/spiffe/login", data=payload, method="POST")
    assert res and "auth" in res, f"Failed SPIFFE JWT login for role {role_name}"
    auth = res["auth"]
    client_token = auth.get("client_token")
    policies = auth.get("policies", [])
    assert client_token, "No client token returned from SPIFFE login"
    return client_token, policies


def test_dynamic_database_credentials():
    res = openbao_request("database/creds/tenant-acme-db-role")
    assert res and "data" in res, "Failed to generate dynamic PostgreSQL credentials"
    db_user = res["data"].get("username")
    db_pass = res["data"].get("password")
    lease_duration = res.get("lease_duration")
    assert db_user and db_pass, "Missing username/password in database creds response"
    assert lease_duration > 0, "Invalid lease duration for dynamic credentials"
    return db_user, db_pass, lease_duration


def test_transit_encryption():
    plaintext = "Darueira Enterprise Zero Trust Payload 2026"
    b64_pt = base64.b64encode(plaintext.encode()).decode()
    enc_res = openbao_request("transit/encrypt/tenant-acme-key", data={"plaintext": b64_pt}, method="POST")
    ciphertext = enc_res["data"]["ciphertext"]
    assert ciphertext.startswith("vault:v1:"), f"Invalid ciphertext format: {ciphertext}"

    dec_res = openbao_request("transit/decrypt/tenant-acme-key", data={"ciphertext": ciphertext}, method="POST")
    decrypted_pt = base64.b64decode(dec_res["data"]["plaintext"]).decode()
    assert decrypted_pt == plaintext, f"Decryption mismatch: {decrypted_pt} vs {plaintext}"
    return ciphertext


def main():
    print("==================================================================")
    print("  Phase 07: SPIRE Workload Identity & OpenBao Validation Suite    ")
    print("==================================================================")

    # 1. SPIRE Server Health & Trust Bundle
    print("\n[1/8] Validating SPIRE Server & Trust Domain ('darueira.local')...")
    bundle = test_spire_server_health()
    print(f"      [✓] SPIRE Server active (Trust Domain: {TRUST_DOMAIN}, Keys: {len(bundle.get('keys', []))})")

    # 2. SPIRE Workload Registration Entries
    print("\n[2/8] Validating Workload Registration Entries in SPIRE Server...")
    registered = test_spire_workload_entries()
    print(f"      [✓] All {len(EXPECTED_WORKLOADS)} workload SPIFFE IDs registered and active")

    # 3. SPIFFE SVID Token Minting
    print("\n[3/8] Validating SPIFFE SVID Issuance & Cryptographic Claims...")
    platform_jwt = mint_jwt_svid(EXPECTED_WORKLOADS[0])
    p_claims = parse_jwt_claims(platform_jwt)
    assert p_claims.get("sub") == EXPECTED_WORKLOADS[0]
    print(f"      [✓] Platform Workload JWT SVID issued: sub={p_claims.get('sub')}")

    acme_jwt = mint_jwt_svid(EXPECTED_WORKLOADS[4])
    a_claims = parse_jwt_claims(acme_jwt)
    assert a_claims.get("sub") == EXPECTED_WORKLOADS[4]
    print(f"      [✓] Tenant Acme JWT SVID issued: sub={a_claims.get('sub')}")

    globex_jwt = mint_jwt_svid(EXPECTED_WORKLOADS[6])
    g_claims = parse_jwt_claims(globex_jwt)
    assert g_claims.get("sub") == EXPECTED_WORKLOADS[6]
    print(f"      [✓] Tenant Globex JWT SVID issued: sub={g_claims.get('sub')}")

    # 4. OpenBao Master PKI Engine
    print("\n[4/8] Validating OpenBao Master PKI Engine & Dynamic mTLS Issuance...")
    cert_data = test_openbao_pki_issue()
    print(f"      [✓] Dynamic X.509 Certificate issued (Serial: {cert_data.get('serial_number')})")

    # 5. OpenBao SPIFFE Workload Authentication
    print("\n[5/8] Validating OpenBao SPIFFE JWT Workload Authentication (auth/spiffe)...")
    platform_token, platform_policies = authenticate_spiffe_jwt_with_openbao(platform_jwt, "platform-admin-role")
    assert "drr-platform-admin" in platform_policies
    print(f"      [✓] Platform workload authenticated -> Policies: {platform_policies}")

    acme_token, acme_policies = authenticate_spiffe_jwt_with_openbao(acme_jwt, "tenant-acme-role")
    assert "tenant-acme" in acme_policies
    print(f"      [✓] Acme workload authenticated -> Policies: {acme_policies}")

    globex_token, globex_policies = authenticate_spiffe_jwt_with_openbao(globex_jwt, "tenant-globex-role")
    assert "tenant-globex" in globex_policies
    print(f"      [✓] Globex workload authenticated -> Policies: {globex_policies}")

    # 6. Multi-Tenant Structured Secrets (KV-v2)
    print("\n[6/8] Validating Multi-Tenant Structured Secrets (KV-v2)...")
    acme_sec = openbao_request("secret/data/tenants/acme/storefront", token=acme_token)
    assert acme_sec["data"]["data"].get("api_key") == "acme-storefront-live-sec-2026"
    print(f"      [✓] Acme token successfully retrieved secret/data/tenants/acme/storefront")

    globex_sec = openbao_request("secret/data/tenants/globex/audit", token=globex_token)
    assert globex_sec["data"]["data"].get("siem_ingest_token") == "globex-audit-token-2026"
    print(f"      [✓] Globex token successfully retrieved secret/data/tenants/globex/audit")

    # 7. Dynamic Database Credentials & Transit Encryption
    print("\n[7/8] Validating Dynamic Database Secrets & Transit Envelope Encryption...")
    db_user, _, ttl = test_dynamic_database_credentials()
    print(f"      [✓] Dynamic PostgreSQL user provisioned: {db_user} (TTL: {ttl}s)")

    ciphertext = test_transit_encryption()
    print(f"      [✓] Transit Encryption-as-a-Service verified (AES-256-GCM envelope)")

    # 8. Zero Trust Multi-Tenant Boundary Isolation
    print("\n[8/8] Validating Zero Trust Multi-Tenant Boundary Enforcement...")
    # Acme CANNOT read Globex
    try:
        openbao_request("secret/data/tenants/globex/audit", token=acme_token)
        assert False, "Acme token was able to read Globex secrets (Security Violation!)"
    except urllib.error.HTTPError as e:
        assert e.code == 403, f"Expected HTTP 403 Forbidden, got {e.code}"
        print("      [✓] Acme token blocked from reading Globex secrets (HTTP 403 Forbidden)")

    # Globex CANNOT read Acme
    try:
        openbao_request("secret/data/tenants/acme/storefront", token=globex_token)
        assert False, "Globex token was able to read Acme secrets (Security Violation!)"
    except urllib.error.HTTPError as e:
        assert e.code == 403, f"Expected HTTP 403 Forbidden, got {e.code}"
        print("      [✓] Globex token blocked from reading Acme secrets (HTTP 403 Forbidden)")

    # Tenant CANNOT read Platform Master secrets
    try:
        openbao_request("secret/data/platform/core", token=acme_token)
        assert False, "Acme token was able to read platform master secrets (Security Violation!)"
    except urllib.error.HTTPError as e:
        assert e.code == 403, f"Expected HTTP 403 Forbidden, got {e.code}"
        print("      [✓] Tenant token blocked from reading platform master secrets (HTTP 403 Forbidden)")

    print("\n==================================================================")
    print("  [✓✓✓] ALL PHASE 07 SPIRE & OPENBAO VALIDATION TESTS PASSED!    ")
    print("==================================================================")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[✗] Validation failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
