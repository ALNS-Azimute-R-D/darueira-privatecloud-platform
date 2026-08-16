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

---

## 7. Administrative Consoles & Reverse Proxy (Magic DNS)

The platform provides unified, friendly browser access to all corporate and tenant administrative consoles through the **Apache APISIX Reverse Proxy Gateway** using **Magic Wildcard DNS (`.127.0.0.1.nip.io`)**.

> [!NOTE]
> **Zero Host Configuration**: You do **NOT** need to edit `/etc/hosts` or install local DNS servers. Any subdomain ending in `.127.0.0.1.nip.io` automatically resolves to your local cluster gateway.

### 7.1 How to Start the Reverse Proxy

Execute one of the following commands in a terminal:

```bash
# Option A: Standard Port 80 (Recommended - Clean URLs with no port numbers)
make proxy-80

# Option B: Non-root Port 9080 (Access via http://<service>...:9080)
make proxy
```

> [!TIP]
> **DNS Rebind Notice**: If your local network router (such as a Fritz!Box) blocks `.nip.io` domains pointing to `127.0.0.1`, enable **"Secure DNS / DNS over HTTPS"** in your browser settings (Chrome/Firefox/Edge $\rightarrow$ Settings $\rightarrow$ Privacy & Security $\rightarrow$ Use Secure DNS $\rightarrow$ Google Public DNS or Cloudflare).

---

### 7.2 Corporate Shared Services Admin Consoles

| Service | Component | Admin Console URL (Port 80) | Default Credentials |
|---|---|---|---|
| **Vault / Secrets** | OpenBao Master | [http://vault.darueira-corpshared.127.0.0.1.nip.io/ui/](http://vault.darueira-corpshared.127.0.0.1.nip.io/ui/) | **Method**: `Token`<br>**Token**: `darueira-root-token` |
| **Identity Provider** | Keycloak Master | [http://keycloak.darueira-corpshared.127.0.0.1.nip.io/admin/](http://keycloak.darueira-corpshared.127.0.0.1.nip.io/admin/) | **User**: `admin`<br>**Password**: `admin123-dev` |
| **Enterprise SSO** | Authentik Server | [http://authentik.darueira-corpshared.127.0.0.1.nip.io](http://authentik.darueira-corpshared.127.0.0.1.nip.io) | **User**: `akadmin`<br>**Password**: `darueira-admin123` |
| **Artifact Registry** | Sonatype Nexus OSS | [http://nexus.darueira-corpshared.127.0.0.1.nip.io](http://nexus.darueira-corpshared.127.0.0.1.nip.io) | **User**: `admin`<br>**Password**: `4ff9b717-0bd0-40ab-b0c9-d53ce21ed155` |
| **Object Storage** | Central MinIO S3 | [http://minio.darueira-corpshared.127.0.0.1.nip.io](http://minio.darueira-corpshared.127.0.0.1.nip.io) | **User**: `minioadmin`<br>**Password**: `minioadmin123` |
| **Metrics Dashboards** | Grafana Obs | [http://grafana.darueira-corpshared.127.0.0.1.nip.io](http://grafana.darueira-corpshared.127.0.0.1.nip.io) | **User**: `admin`<br>**Password**: `admin-dev` |
| **Log Analytics** | OpenSearch Dashboards | [http://opensearch.darueira-corpshared.127.0.0.1.nip.io](http://opensearch.darueira-corpshared.127.0.0.1.nip.io) | *(Direct Access / SSO)* |
| **Metrics Engine** | Prometheus Engine | [http://prometheus.darueira-corpshared.127.0.0.1.nip.io](http://prometheus.darueira-corpshared.127.0.0.1.nip.io) | *(Direct Access)* |
| **Distributed Tracing** | Jaeger Tracing UI | [http://jaeger.darueira-corpshared.127.0.0.1.nip.io](http://jaeger.darueira-corpshared.127.0.0.1.nip.io) | *(Direct Access)* |
| **ReBAC Explorer** | OpenFGA Playground | [http://openfga.darueira-corpshared.127.0.0.1.nip.io](http://openfga.darueira-corpshared.127.0.0.1.nip.io) | *(Direct Access)* |
| **Developer Portal** | Spotify Backstage | [http://backstage.darueira-corpshared.127.0.0.1.nip.io](http://backstage.darueira-corpshared.127.0.0.1.nip.io) | *(SSO Authentik)* |
| **GitOps Engine** | ArgoCD Console | [http://argocd.darueira-corpshared.127.0.0.1.nip.io](http://argocd.darueira-corpshared.127.0.0.1.nip.io) | **User**: `admin`<br>**Password**: `dev-password` |

---

### 7.3 Isolated Tenant Admin Consoles (Example: Tenant `acme`)

Every tenant provisioned on the platform automatically receives dedicated, isolated instances of Vault, Keycloak, and MinIO:

| Tenant Service | Admin Console URL (Port 80) | Default Credentials |
|---|---|---|
| **Tenant Vault** | [http://vault.darueira-tnt-acme.127.0.0.1.nip.io/ui/](http://vault.darueira-tnt-acme.127.0.0.1.nip.io/ui/) | **Method**: `Token`<br>**Token**: `tenant-vault-root-token-2026` |
| **Tenant Keycloak** | [http://keycloak.darueira-tnt-acme.127.0.0.1.nip.io/admin/](http://keycloak.darueira-tnt-acme.127.0.0.1.nip.io/admin/) | **User**: `drr_tenant_admin`<br>**Password**: `tenant_keycloak_pass_2026` |
| **Tenant MinIO S3** | [http://minio.darueira-tnt-acme.127.0.0.1.nip.io](http://minio.darueira-tnt-acme.127.0.0.1.nip.io) | **User**: `minioadmin`<br>**Password**: `minioadmin123` |

> [!NOTE]
> **Dynamic Tenant Routing Formula**:
> Any newly provisioned tenant `<tenant-alias>` follows the standard naming scheme:
> `http://<service-name>.darueira-tnt-<tenant-alias>.127.0.0.1.nip.io`


