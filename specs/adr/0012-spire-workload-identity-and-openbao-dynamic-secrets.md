# ADR 0012: Zero Trust Workload Identity with SPIRE and Dynamic Secrets with OpenBao PKI

## Status
Accepted

## Context
In a multi-tenant, zero-trust cloud-native platform, workloads running across platform and tenant namespaces must never rely on static API tokens, long-lived database passwords, or hardcoded credentials. 

To achieve true Zero Trust security:
1. Every workload must have a cryptographically verifiable identity rooted in the cluster control plane (**SPIFFE ID**).
2. Secrets must be generated dynamically on-demand with short time-to-live (TTL) and automatic revocation.
3. Access to platform secrets, databases, transit encryption keys, and PKI certificates must be gated strictly by the workload's authenticated SPIFFE identity.

## Decision
1. **SPIRE (SPIFFE Runtime Environment) for Workload Identity**:
   - Deploy **SPIRE Server** (`drr-corpshared-secr-internal`) under Trust Domain `darueira.local`.
   - Issue **X.509 SVIDs** and **JWT SVIDs** to workloads based on Kubernetes pod and service account selectors (`spiffe://darueira.local/ns/{namespace}/sa/{serviceaccount}`).
   - Provide workload registration entries for platform control plane services (`drr-iam-authz-svc`, `drr-tenant-svc`, `drr-env-orchestrator-svc`, `drr-operator`) and tenant workloads (`acme-storefront-app`, `acme-logistics-svc`, `globex-security-audit`).

2. **OpenBao Master for Dynamic Secrets & Master PKI**:
   - Deploy **OpenBao Master** in `drr-corpshared-secr-internal`.
   - **PKI Secret Engine** (`pki/` & `pki_int/`): Manage Root CA and Intermediate CA for issuing dynamic mTLS certificates with 24h default TTL.
   - **SPIFFE JWT Auth Method** (`auth/spiffe`): Federate directly with SPIRE Server JWKS, allowing workloads to authenticate using their SPIFFE JWT SVIDs and receive short-lived Vault tokens bound to fine-grained tenant policies.
   - **Dynamic Database Secrets Engine** (`database/`): Provision just-in-time, short-lived PostgreSQL credentials (1h TTL) dynamically generated on Central PostgreSQL.
   - **Transit Encryption Engine** (`transit/`): Deliver Encryption-as-a-Service (AES-256-GCM envelope encryption) for multi-tenant sensitive data protection.
   - **KV-v2 Secrets Engine** (`secret/`): Provide structured, versioned multi-tenant configuration secrets.

## Consequences
- **Zero Static Credentials**: Applications acquire temporary credentials through SPIFFE identity without storing passwords in repositories or environment variables.
- **Strict Multi-Tenant Isolation**: OpenBao policies enforce tenant boundaries (e.g. Acme workload tokens cannot read Globex secrets or platform master keys).
- **Automated Lifecycle**: Certificates, database roles, and tokens rotate automatically based on short-lived TTLs.
