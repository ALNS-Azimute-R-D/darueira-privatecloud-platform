# Darueira Private Cloud Platform (`darueira-privatecloud-platform`)

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Kubernetes: MicroK8s](https://img.shields.io/badge/Kubernetes-MicroK8s-326CE5.svg?logo=kubernetes&logoColor=white)](https://microk8s.io)
[![Networking: Cilium eBPF](https://img.shields.io/badge/CNI-Cilium%20eBPF-F05032.svg?logo=cilium&logoColor=white)](https://cilium.io)
[![Authz: OpenFGA ReBAC](https://img.shields.io/badge/Authz-OpenFGA%20ReBAC-5D3FD3.svg)](https://openfga.dev)

An enterprise-grade, on-premise **Private Cloud and Internal Developer Platform (IDP)** designed for high-performance workloads, multi-tenancy, spec-driven development (SDD), and native Zero Trust security running on Canonical MicroK8s.

---

## 1. Architectural Highlights

- **Runtime & CNI**: Canonical **MicroK8s** with **Cilium CNI** (eBPF-based L3-L7 NetworkPolicies, transparent WireGuard node-to-node encryption, and kube-proxy replacement).
- **Ingress & LoadBalancer**: MicroK8s **MetalLB** IP pool + **Apache APISIX** Ingress DataPlane.
- **Hybrid Identity & Access**:
  - **Coarse-Grained Authentication**: **Authentik** (Enterprise Directory / IdP) and Keycloak.
  - **Fine-Grained Authorization (ReBAC)**: **OpenFGA** with Zanzibar relationship model (`authz/schema.fga`).
  - **In-Pod Workload Enforcement (PEP/PDP)**: **Envoy Proxy** (`envoy.filters.http.ext_authz`) as PEP paired with **OPA** as PDP over local gRPC (`127.0.0.1:9191`) with 0.25s timeout and fail-closed security.
- **Native Zero Trust**:
  - Workload identity via **SPIFFE/SPIRE** X.509 SVIDs.
  - Dynamic ephemeral secret retrieval via **OpenBao (Vault)** with SPIFFE Auth and CSI Driver.
- **Dedicated Persistence**:
  - Central Shared Services maintain dedicated **System PostgreSQL** and **System MinIO** instances, decoupled from tenant workloads.
- **Declarative CI/CD & GitOps**:
  - In-cluster task and pipeline execution via **Tekton Pipelines**.
  - Continuous delivery and state reconciliation via **ArgoCD**.
- **Internal Developer Portal**:
  - **Spotify Backstage** for software catalog, golden path templates, and TechDocs.

---

## 2. Trust Domains & Namespace Hierarchy

```
+-----------------------------------------------------------------------------------+
|                     ENTERPRISE SHARED SERVICES (CONTROL PLANE)                    |
|   Namespaces: drr-corpshared-mgmt | drr-corpshared-plat | drr-corpshared-secr-internal |
+-----------------------------------------------------------------------------------+
|  * Master IdP: Authentik Central (OIDC / OAuth2 / SAML)                           |
|  * Universal Artifact Registry: Sonatype Nexus OSS (Docker, Helm, Maven)          |
|  * Corporate Mail Server: Stalwart Mail Server (SMTP, IMAP)                       |
|  * Master PKI / Vault: OpenBao Master + SPIRE Server                              |
|  * Developer Portal: Spotify Backstage                                            |
|  * Central Persistence: Central PostgreSQL + Central MinIO (S3 Blobs)             |
|  * Declarative CI/CD & GitOps: Tekton Pipelines & Triggers + ArgoCD               |
+-----------------------------------------------------------------------------------+
                                         |
                                         | SPIFFE mTLS / OpenFGA ReBAC
                                         v
+-----------------------------------------------------------------------------------+
|                             TENANT ENVIRONMENT PLANE                              |
|          Namespaces: drr-tnt-{tenant-id}-{project-id}-{env} (Dev, Staging, Prod)      |
+-----------------------------------------------------------------------------------+
|  * Edge & Ingress: Apache APISIX DataPlane                                        |
|  * In-Pod Enforcement: Envoy Proxy PEP + OPA PDP Sidecars (ext_authz :9191)       |
|  * Dynamic Secrets: OpenBao Tenant Mounts via SPIFFE SVID                          |
|  * Tenant Storage: MinIO Dedicated Buckets + CloudNative-PG / MongoDB              |
|  * Event Streaming & Messaging: Apache Kafka (Strimzi) + RabbitMQ                 |
|  * Workload Identity: SPIRE Agent Pod Attestation                                 |
+-----------------------------------------------------------------------------------+
```

---

## 3. Polyglot Monorepo Scaffolding

```
darueira-privatecloud-platform/
├── apps/
│   ├── backstage/                   # Developer Portal (Spotify Backstage)
│   ├── drr-ctlr-cli/                # Developer & Admin CLI (drr-ctlr-cli)
│   ├── drr-env-orchestrator-svc/    # Environment Engine & CRD Translator
│   ├── drr-iam-authz-svc/           # IAM & OpenFGA Authorization Gateway
│   └── drr-tenant-svc/              # Tenant & Project Lifecycle Manager
├── authz/
│   ├── schema.fga                   # OpenFGA ReBAC Model (DSL v1.2)
│   └── tests.fga.yaml               # Automated ReBAC Test Assertions (136+ checks)
├── operators/
│   └── darueira-operator/           # Core K8s Operator reconciling Tenants/Environments
├── platform/
│   ├── bootstrap/
│   │   ├── 00-setup-microk8s.sh     # MicroK8s, Addons, Cilium, MetalLB Setup
│   │   └── 01-deploy-control-plane.sh # Enterprise Shared Services Bootstrap
│   ├── gitops/
│   │   ├── argocd-apps/             # ArgoCD ApplicationSets & Manifests
│   │   └── tekton-pipelines/        # Tekton Pipeline & Task Definitions
│   └── kustomize/
│       └── base/
│           ├── corpshared-mgmt/     # Backstage, ArgoCD, Tekton Engine
│           ├── corpshared-plat/     # Central Postgres, MinIO, Nexus, Stalwart, Authentik
│           ├── corpshared-secr-internal/ # OpenBao Master, SPIRE Server
│           └── tnt-tenant-base/     # Tenant baseline (Envoy PEP, OPA PDP patch, Quotas)
├── specs/
│   ├── 01-initial-spec.md           # Master Platform Specification
│   └── adr/                         # Architecture Decision Records (ADR 0001 - 0004)
├── AGY.md                           # Antigravity Agent Guidelines & SDD Protocols
├── Makefile                         # Developer Automation Targets
└── README.md                        # Project Documentation
```

---

## 4. Prerequisites

- **Operating System**: Linux Mint 22.3 (or Ubuntu 24.04 LTS derivative)
- **Hardware**: Intel Core i9 (or equivalent), 64 GB RAM, 20 vCPUs
- **Installed Tools**:
  - Canonical MicroK8s (`sudo snap install microk8s --classic`)
  - OpenFGA CLI (`go install github.com/openfga/cli/cmd/fga@latest`)
  - Go Toolchain (`go version >= 1.22`)
  - Java 25 & Kotlin 2.4 (via SDKMAN)
  - `kubectl`, `make`, `curl`, `docker`

---

## 5. Quickstart & Step-by-Step Operations

### Step 1: Validate ReBAC Authorization Model
Run the OpenFGA test suite validating inheritance, deployer boundaries, and strict multi-tenant isolation:
```bash
make test-authz
```
*Output: 4/4 test suites passing, 136/136 checks passing.*

### Step 2: Validate Kustomize Manifests
Validate that all enterprise control plane and tenant base manifests render correctly:
```bash
make validate-manifests
```

### Step 3: Setup MicroK8s Runtime & Network Addons
Bootstrap MicroK8s addons (DNS, Hostpath storage, RBAC, local container registry, MetalLB) and verify Cilium CNI:
```bash
make microk8s-setup
```

### Step 4: Bootstrap Enterprise Control Plane
Initialize core namespaces (`drr-corpshared-secr-internal`, `drr-corpshared-plat`, `drr-corpshared-mgmt`) and deploy baseline services (Authentik, Central Postgres, Central MinIO, OpenBao, Backstage, Tekton, ArgoCD):
```bash
make bootstrap-control-plane
```

### Step 5: Build Platform Services & Images
Build local binaries and container images tagged for the local MicroK8s registry (`localhost:32000`):
```bash
make build-all
```

---

## 6. Security Standards

- **Strict Non-Root Containers**: Workloads run under unprivileged UID `10001` (`runAsNonRoot: true`, `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`).
- **No Static Credentials**: Dynamic SPIFFE/SPIRE workload attestation and OpenBao ephemeral secret generation.
- **eBPF Network Isolation**: Strict CiliumNetworkPolicies enforcing default-deny and explicit tenant boundary rules.
