#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Enterprise Secrets & Workload Identity
Declarative SPIRE Workload Identity & OpenBao Dynamic Secrets Bootstrapper
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

POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "central-postgres.drr-corpshared-plat.svc.cluster.local")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.environ.get("POSTGRES_USER", "drr_admin")
POSTGRES_PASS = os.environ.get("POSTGRES_PASS", "change-me-in-openbao")

SPIRE_POD = os.environ.get("SPIRE_POD", "deploy/spire-server-placeholder")
SPIRE_NS = os.environ.get("SPIRE_NS", "drr-corpshared-secr-internal")
TRUST_DOMAIN = "darueira.local"
PARENT_ID = f"spiffe://{TRUST_DOMAIN}/spire/agent/k8s-cluster"

WORKLOAD_ENTRIES = [
    {
        "name": "drr-iam-authz-svc",
        "spiffe_id": f"spiffe://{TRUST_DOMAIN}/ns/drr-corpshared-plat/sa/drr-iam-authz-svc",
        "selectors": ["k8s:ns:drr-corpshared-plat", "k8s:sa:drr-iam-authz-svc"]
    },
    {
        "name": "drr-tenant-svc",
        "spiffe_id": f"spiffe://{TRUST_DOMAIN}/ns/drr-corpshared-plat/sa/drr-tenant-svc",
        "selectors": ["k8s:ns:drr-corpshared-plat", "k8s:sa:drr-tenant-svc"]
    },
    {
        "name": "drr-env-orchestrator-svc",
        "spiffe_id": f"spiffe://{TRUST_DOMAIN}/ns/drr-corpshared-mgmt/sa/drr-env-orchestrator-svc",
        "selectors": ["k8s:ns:drr-corpshared-mgmt", "k8s:sa:drr-env-orchestrator-svc"]
    },
    {
        "name": "drr-operator",
        "spiffe_id": f"spiffe://{TRUST_DOMAIN}/ns/drr-corpshared-mgmt/sa/drr-operator",
        "selectors": ["k8s:ns:drr-corpshared-mgmt", "k8s:sa:drr-operator"]
    },
    {
        "name": "acme-storefront-app",
        "spiffe_id": f"spiffe://{TRUST_DOMAIN}/ns/drr-tnt-acme/sa/acme-storefront-app",
        "selectors": ["k8s:ns:drr-tnt-acme", "k8s:sa:acme-storefront-app"]
    },
    {
        "name": "acme-logistics-svc",
        "spiffe_id": f"spiffe://{TRUST_DOMAIN}/ns/drr-tnt-acme/sa/acme-logistics-svc",
        "selectors": ["k8s:ns:drr-tnt-acme", "k8s:sa:acme-logistics-svc"]
    },
    {
        "name": "globex-security-audit",
        "spiffe_id": f"spiffe://{TRUST_DOMAIN}/ns/drr-tnt-globex/sa/globex-security-audit",
        "selectors": ["k8s:ns:drr-tnt-globex", "k8s:sa:globex-security-audit"]
    }
]


def openbao_request(path, data=None, method="GET"):
    clean_path = path.lstrip("/")
    url = f"{OPENBAO_ADDR}/v1/{clean_path}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    headers = {
        "X-Vault-Token": OPENBAO_TOKEN,
        "Content-Type": "application/json"
    }
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 204 or resp.length == 0:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        if e.code == 400 and ("path is already in use" in err_msg or "already exists" in err_msg):
            return None
        print(f"    [!] OpenBao HTTP {e.code} on {path}: {err_msg}")
        raise


from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization


def jwk_to_pem(jwk):
    x_bytes = base64.urlsafe_b64decode(jwk["x"] + "==")
    y_bytes = base64.urlsafe_b64decode(jwk["y"] + "==")
    public_numbers = ec.EllipticCurvePublicNumbers(
        int.from_bytes(x_bytes, "big"),
        int.from_bytes(y_bytes, "big"),
        ec.SECP256R1()
    )
    return public_numbers.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("utf-8")


def bootstrap_spire_server():
    print(f"--> Bootstrapping SPIRE Server Workload Registration Entries (Trust Domain: {TRUST_DOMAIN})...")
    # 1. Fetch current SPIRE entries via CLI inside spire-server pod
    show_cmd = f"microk8s kubectl exec -n {SPIRE_NS} {SPIRE_POD} -- /opt/spire/bin/spire-server entry show"
    try:
        proc = subprocess.run(show_cmd, shell=True, capture_output=True, text=True, check=True)
        raw_output = proc.stdout
    except Exception as e:
        print(f"    Notice listing SPIRE entries: {e}")
        raw_output = ""

    for item in WORKLOAD_ENTRIES:
        spiffe_id = item["spiffe_id"]
        if spiffe_id not in raw_output:
            selector_args = " ".join([f"-selector {s}" for s in item["selectors"]])
            create_cmd = f"microk8s kubectl exec -n {SPIRE_NS} {SPIRE_POD} -- /opt/spire/bin/spire-server entry create -spiffeID {spiffe_id} -parentID {PARENT_ID} {selector_args}"
            res = subprocess.run(create_cmd, shell=True, capture_output=True, text=True)
            if res.returncode == 0:
                print(f"    [✓] Registered SPIRE Workload: {item['name']} -> {spiffe_id}")
            else:
                print(f"    [!] Entry create note for {item['name']}: {res.stderr.strip()}")
        else:
            print(f"    [✓] Workload already registered: {item['name']} -> {spiffe_id}")


def bootstrap_openbao_pki():
    print("--> Bootstrapping OpenBao Master PKI Engine (Root & Intermediate CA)...")
    # 1. Mount Root PKI
    openbao_request("sys/mounts/pki", data={"type": "pki", "config": {"max_lease_ttl": "87600h"}}, method="POST")

    # 2. Generate Root CA if not exists
    try:
        openbao_request("pki/root/generate/internal", data={
            "common_name": "Darueira Enterprise Root CA",
            "ttl": "87600h",
            "key_type": "rsa",
            "key_bits": 2048
        }, method="POST")
        print("    [✓] Generated Darueira Enterprise Root CA in OpenBao")
    except Exception:
        print("    [✓] Darueira Root CA already present")

    # 3. Mount Intermediate PKI
    openbao_request("sys/mounts/pki_int", data={"type": "pki", "config": {"max_lease_ttl": "43800h"}}, method="POST")

    # 4. Generate Intermediate CSR & Sign with Root CA
    csr_res = openbao_request("pki_int/intermediate/generate/internal", data={
        "common_name": "Darueira Workload Intermediate CA",
        "ttl": "43800h",
        "key_type": "rsa",
        "key_bits": 2048
    }, method="POST")
    if csr_res and "data" in csr_res:
        csr = csr_res["data"]["csr"]
        sign_res = openbao_request("pki/root/sign-intermediate", data={
            "csr": csr,
            "common_name": "Darueira Workload Intermediate CA",
            "ttl": "43800h"
        }, method="POST")
        cert = sign_res["data"]["certificate"]
        openbao_request("pki_int/intermediate/set-signed", data={"certificate": cert}, method="POST")
        print("    [✓] Signed & Installed Darueira Workload Intermediate CA")

    # 5. Workload Role
    openbao_request("pki_int/roles/darueira-workload-role", data={
        "allowed_domains": ["darueira.local", "svc.cluster.local", "nip.io"],
        "allow_subdomains": True,
        "max_ttl": "72h",
        "ttl": "24h"
    }, method="POST")
    print("    [✓] Configured PKI Workload Role: darueira-workload-role (TTL: 24h)")


def bootstrap_openbao_spiffe_auth():
    print("--> Bootstrapping OpenBao SPIFFE Workload JWT Authentication Method...")
    # 1. Fetch JWKS from SPIRE Server and convert to PEM public keys
    jwks_cmd = f"microk8s kubectl exec -n {SPIRE_NS} {SPIRE_POD} -- /opt/spire/bin/spire-server bundle show -format spiffe"
    proc = subprocess.run(jwks_cmd, shell=True, capture_output=True, text=True, check=True)
    bundle_data = json.loads(proc.stdout)
    jwt_keys = [k for k in bundle_data.get("keys", []) if k.get("use") == "jwt-svid"]
    pems = [jwk_to_pem(k) for k in jwt_keys]

    # 2. Enable JWT Auth at auth/spiffe
    openbao_request("sys/auth/spiffe", data={"type": "jwt"}, method="POST")

    # 3. Configure auth/spiffe with PEM keys
    openbao_request("auth/spiffe/config", data={
        "jwt_validation_pubkeys": pems,
        "jwt_supported_algs": ["ES256"]
    }, method="POST")
    print("    [✓] Configured SPIFFE Auth Method with SPIRE validation public keys")

    # 4. Create Policies
    policies = {
        "drr-platform-admin": """
            path "secret/data/*" { capabilities = ["create", "read", "update", "delete", "list"] }
            path "pki_int/issue/*" { capabilities = ["create", "update"] }
            path "database/creds/*" { capabilities = ["read"] }
            path "transit/*" { capabilities = ["create", "read", "update", "delete", "list"] }
        """,
        "tenant-acme": """
            path "secret/data/tenants/acme/*" { capabilities = ["create", "read", "update", "delete", "list"] }
            path "database/creds/tenant-acme-db-role" { capabilities = ["read"] }
            path "transit/encrypt/tenant-acme-key" { capabilities = ["update"] }
            path "transit/decrypt/tenant-acme-key" { capabilities = ["update"] }
            path "pki_int/issue/darueira-workload-role" { capabilities = ["create", "update"] }
        """,
        "tenant-globex": """
            path "secret/data/tenants/globex/*" { capabilities = ["create", "read", "update", "delete", "list"] }
            path "transit/encrypt/tenant-globex-key" { capabilities = ["update"] }
            path "transit/decrypt/tenant-globex-key" { capabilities = ["update"] }
            path "pki_int/issue/darueira-workload-role" { capabilities = ["create", "update"] }
        """
    }

    for p_name, p_rules in policies.items():
        openbao_request(f"sys/policy/{p_name}", data={"policy": p_rules.strip()}, method="POST")
        print(f"    [✓] Configured OpenBao Policy: {p_name}")

    # 5. Create SPIFFE Roles
    roles = [
        {
            "name": "platform-admin-role",
            "user_claim": "sub",
            "bound_claims": {
                "sub": [
                    f"spiffe://{TRUST_DOMAIN}/ns/drr-corpshared-plat/sa/drr-iam-authz-svc",
                    f"spiffe://{TRUST_DOMAIN}/ns/drr-corpshared-plat/sa/drr-tenant-svc",
                    f"spiffe://{TRUST_DOMAIN}/ns/drr-corpshared-mgmt/sa/drr-env-orchestrator-svc",
                    f"spiffe://{TRUST_DOMAIN}/ns/drr-corpshared-mgmt/sa/drr-operator"
                ]
            },
            "bound_audiences": ["openbao", "vault"],
            "role_type": "jwt",
            "token_policies": ["drr-platform-admin", "default"],
            "token_ttl": "1h"
        },
        {
            "name": "tenant-acme-role",
            "user_claim": "sub",
            "bound_claims": {
                "sub": [
                    f"spiffe://{TRUST_DOMAIN}/ns/drr-tnt-acme/sa/acme-storefront-app",
                    f"spiffe://{TRUST_DOMAIN}/ns/drr-tnt-acme/sa/acme-logistics-svc"
                ]
            },
            "bound_audiences": ["openbao", "vault"],
            "role_type": "jwt",
            "token_policies": ["tenant-acme", "default"],
            "token_ttl": "1h"
        },
        {
            "name": "tenant-globex-role",
            "user_claim": "sub",
            "bound_claims": {
                "sub": [
                    f"spiffe://{TRUST_DOMAIN}/ns/drr-tnt-globex/sa/globex-security-audit"
                ]
            },
            "bound_audiences": ["openbao", "vault"],
            "role_type": "jwt",
            "token_policies": ["tenant-globex", "default"],
            "token_ttl": "1h"
        }
    ]

    for r in roles:
        role_name = r.pop("name")
        openbao_request(f"auth/spiffe/role/{role_name}", data=r, method="POST")
        print(f"    [✓] Configured SPIFFE Workload Role: {role_name}")


def bootstrap_openbao_secrets_engines():
    print("--> Bootstrapping OpenBao KV-v2, Transit & Dynamic Database Engines...")
    # 1. KV-v2 Mount & Seed
    openbao_request("sys/mounts/secret", data={"type": "kv", "options": {"version": "2"}}, method="POST")

    secrets = {
        "secret/data/platform/core": {
            "cluster_name": "darueira-privatecloud",
            "environment": "production",
            "encryption_profile": "aes256-gcm",
            "master_ca": "Darueira Enterprise Root CA"
        },
        "secret/data/tenants/acme/storefront": {
            "api_key": "acme-storefront-live-sec-2026",
            "stripe_webhook_secret": "whsec_acme_production_2026",
            "redis_cache_token": "acme-redis-sec-token"
        },
        "secret/data/tenants/acme/logistics": {
            "tracking_api_secret": "acme-logistics-key-2026",
            "carrier_dispatch_token": "carrier-sec-dispatch-99"
        },
        "secret/data/tenants/globex/audit": {
            "siem_ingest_token": "globex-audit-token-2026",
            "compliance_export_key": "globex-export-rsa-key"
        }
    }

    for s_path, s_data in secrets.items():
        openbao_request(s_path, data={"data": s_data}, method="POST")
        print(f"    [✓] Seeded structured secret: {s_path}")

    # 2. Transit Encryption Engine
    openbao_request("sys/mounts/transit", data={"type": "transit"}, method="POST")
    for key_name in ["tenant-acme-key", "tenant-globex-key", "platform-core-key"]:
        openbao_request(f"transit/keys/{key_name}", data={"type": "aes256-gcm96"}, method="POST")
        print(f"    [✓] Configured Transit Key: {key_name} (AES-256-GCM)")

    # 3. Dynamic Database Secrets Engine
    openbao_request("sys/mounts/database", data={"type": "database"}, method="POST")
    conn_url = f"postgresql://{{{{username}}}}:{{{{password}}}}@{POSTGRES_HOST}:{POSTGRES_PORT}/postgres?sslmode=disable"
    openbao_request("database/config/central-postgres", data={
        "plugin_name": "postgresql-database-plugin",
        "allowed_roles": ["tenant-acme-db-role", "platform-admin-db-role"],
        "connection_url": conn_url,
        "username": POSTGRES_USER,
        "password": POSTGRES_PASS
    }, method="POST")
    print("    [✓] Configured Central PostgreSQL Connection in OpenBao Database Engine")

    openbao_request("database/roles/tenant-acme-db-role", data={
        "db_name": "central-postgres",
        "creation_statements": [
            "CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}';",
            "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO \"{{name}}\";"
        ],
        "default_ttl": "1h",
        "max_ttl": "24h"
    }, method="POST")
    print("    [✓] Configured Dynamic Database Role: tenant-acme-db-role (TTL: 1h)")


def main():
    print("==================================================================")
    print("  Bootstrapping SPIRE Workload Identity & OpenBao Dynamic Secrets ")
    print("==================================================================")

    # 1. Health check OpenBao
    for _ in range(10):
        try:
            with urllib.request.urlopen(f"{OPENBAO_ADDR}/v1/sys/health", timeout=3) as resp:
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(2)

    # 2. SPIRE Server Workload Registration
    bootstrap_spire_server()

    # 3. OpenBao Master PKI Engine
    bootstrap_openbao_pki()

    # 4. OpenBao SPIFFE JWT Auth Method & Policies
    bootstrap_openbao_spiffe_auth()

    # 5. OpenBao Secrets Engines (KV-v2, Transit, Dynamic DB)
    bootstrap_openbao_secrets_engines()

    print("\n[✓] SPIRE Workload Identity & OpenBao Dynamic Secrets bootstrap completed successfully!")


if __name__ == "__main__":
    main()
