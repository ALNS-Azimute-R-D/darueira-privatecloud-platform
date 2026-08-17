# Master Platform Specification (01-initial-spec.md)
# Project: darueira-privatecloud-platform

## 1. Executive Summary & Vision
`darueira-privatecloud-platform` is an on-premise Private Cloud and Internal Developer Platform (IDP) designed to deliver self-service, secure, and standardized environment provisioning across multiple Tenants and Projects.

### 1.1 Overview & Architecture Goals
The **Darueira Private Cloud Platform** is an enterprise-grade local/private Kubernetes infrastructure designed for high-performance backend workloads, multi-tenancy, zero-trust security, and observable microservice ecosystems.

Inspired by enterprise platform architectures (such as Tesla Cloud Platform - TCP and EDP/50-Hertz/MCCS), it integrates native Zero Trust security, declarative Kubernetes orchestration, polyglot microservices, dynamic secrets management, unified CI/CD with Tekton + ArgoCD, dedicated control plane persistence, and hybrid authorization (OIDC + ReBAC).

---

## 2. Infrastructure & Runtime Baseline
- **Target Host**: Linux Mint 22.3 (64 GB RAM, Intel Core i9, 20 vCPUs). (Personal Laptop)
  - **Compute Resources:** 20 vCPUs, 64 GB RAM, Multi-core optimization
* **Runtime / Orchestration:**
  - **Kubernetes Engine**: **Canonical MicroK8s** (snap-based local system daemon).
  - **Container Runtime**: `containerd` / Docker
  - **Storage**: MinIO (S3-compatible Object Storage), Local Persistent Volumes
- **CNI & Mesh**: **Cilium CNI** (eBPF routing, L3-L7 NetworkPolicies, WireGuard node-to-node encryption, kube-proxy replacement).
- **LoadBalancer / Ingress**: MicroK8s MetalLB + Apache APISIX Ingress Controller.
- **Future Hybrid Target**: Remote VPS (Hostinger) for staging/production external simulation.

---
## 3. High-Level Architecture & Component Topology

                  +----------------------------------------------+
                  |            API Gateway (Apache APISIX)       |
                  |     (mTLS + OIDC Authentik / Token Validate) |
                  +-----------------------+----------------------+
                                          |
         +--------------------------------+--------------------------------+
         |                                |                                |
         v                                v                                v
+-------------------+           +-------------------+            +-------------------+
|  Tenant & Project |           | Environment       |            | Identity & Authz  |
|  Manager Service  |           | Engine Service    |            | Service (OpenFGA) |
|   (Golang/Java)   |           |  (Golang/K8s SDK) |            |    (Go/Kotlin)    |
+---------+---------+           +---------+---------+            +---------+---------+
          |                               |                                |
          +-------------------------------+--------------------------------+
          |
          v
+-----------------------+
|   darueira-operator   |
|   (K8s CRDs Controller|
|   + Tekton / GitOps)  |
+-----------------------+


### Core Control Plane Services
1. **`drr-iam-authz-svc`** (Go / Kotlin): Authorization gateway verifying OIDC claims against Keycloak/Authentik and evaluating ReBAC tuples in OpenFGA.
2. **`drr-tenant-svc`** (Java 25 / Spring Boot 4.1.0 / Kotlin or Go): Lifecycle management for Tenants/Organizations, Projects, and resource quotas.
3. **`drr-env-orchestrator-svc`** (Go): Translates environment specifications into Custom Resources (CRDs) and triggers Tekton Pipelines and ArgoCD ApplicationSets.
4. **`drr-operator`** (Go / Kubebuilder): Kubernetes Operator reconciling Tenant Namespaces, Cilium Network Policies, Vault bindings, and SPIRE registrations.
5. **`drr-ctlr-cli`** (Go / Cobra): Developer and platform administrator CLI tool.

### 3.1 Core Platform Components

#### 3.1.1. Identity, Access & Secrets Management (IAM / Security)
* **Authentication & Identity Provider:** Keycloak / Authentik (OIDC, OAuth2, SAML)
* **Fine-Grained Authorization (ReBAC / RBAC):** OpenFGA (Relationship-Based Access Control)
* **Secrets Management:** OpenBao / HashiCorp Vault (PKI, dynamic secrets, transit encryption)

#### 3.1.2. Data & Messaging Services
* **Databases:** PostgreSQL (Relational), MongoDB (Document)
* **Event Streaming & Async Messaging:**
    * Apache Kafka (Event streaming)
    * RabbitMQ (AMQP message broker)

#### 3.1.3. Observability & Operations
* **Metrics & Dashboards:** Prometheus + Grafana
* **Distributed Tracing:** OpenTelemetry + Jaeger
* **Logs:** OpenSearch
* **GitOps & Delivery:** ArgoCD + Tekton
* **Developer Portal:** Backstage

---

## 4. Trust Domains & Services Topology

Following the MCCS / EDP / 50Hz trust domain separation model, the platform segregates central shared services from isolated tenant workloads.

+-----------------------------------------------------------------------------------+
|                     ENTERPRISE SHARED SERVICES (CONTROL PLANE)                    |
|   Namespaces: drr-corpshared-mgmt | drr-corpshared-plat | drr-corpshared-secr-internal        |
+-----------------------------------------------------------------------------------+
|  * Master Identity Provider: Authentik (Enterprise AD / EntraID Mock)             |
|  * Master PKI & Root Vault: OpenBao Central (Root CA + Intermediate CAs)          |
|  * Universal Artifact & Image Registry: Sonatype Nexus OSS (Docker, Helm, Maven)  |
|  * Corporate Mail Server: Stalwart Mail Server (SMTP, IMAP, JMAP via Authentik)   |
|  * Developer Portal (IDP): Spotify Backstage (Catalog, TechDocs, Golden Paths)   |
|  * Control Plane Storage & Persistence (Dedicated):                               |
|      - Central MinIO: S3 Blobs for Nexus, Backstage TechDocs, Stalwart, Tekton    |
|      - Central PostgreSQL: Dedicated DBs for Authentik, OpenFGA, Backstage, Mail  |
|  * Declarative CI/CD Pipelines: Tekton Pipelines & Triggers                       |
|  * GitOps Continuous Delivery: ArgoCD                                             |
|  * Central APM & Observability: SigNoz, OpenSearch, Prometheus, Grafana           |
+-----------------------------------------------------------------------------------+
|
| SPIFFE mTLS / OpenFGA ReBAC / APISIX
v
+-----------------------------------------------------------------------------------+
|                             TENANT ENVIRONMENT PLANE                              |
|          Namespaces: drr-tnt-{tenant-id}-{project-id}-{env} (Dev, Staging, Prod)      |
+-----------------------------------------------------------------------------------+
|  * Tenant Ingress & Edge: Apache APISIX DataPlane                                 |
|  * Local IAM: Keycloak / Clavex (Federated via OIDC with Authentik Central)       |
|  * Dynamic Secrets: OpenBao Tenant Mount (Authenticated via SPIFFE X.509 SVID)    |
|  * Tenant Object Storage: MinIO (Dedicated buckets with tenant IAM policies)      |
|  * Dedicated Data Stores: PostgreSQL (CloudNative-PG) & MongoDB                   |
|  * Message Brokers: Apache Kafka (Strimzi) & RabbitMQ (VHost / Topic RBAC)       |
|  * Workload Identity: SPIRE Agent (Injecting SVIDs into application pods)         |
+-----------------------------------------------------------------------------------+

### 4.1 Development & Workflow Conventions

* **Methodology:** Spec-Driven Development (SDD)
* **Tooling Integration:** Local AI agents & IDE specifications (`.antigravity` / prompt specs)
* **Validation Criteria:**
    * All deployments managed via Declarative GitOps manifests / Helm charts.
    * Secrets must never be stored in plain text; dynamic injection via Secret Operator / Vault / OpenBao.
    * Relationship-based access queries verified against OpenFGA models prior to service access.

---

## 5. Comprehensive Services Matrix

| Domain | Technology | Delivery Scope | Authentication / Governance |
| :--- | :--- | :--- | :--- |
| **Developer Portal** | Spotify Backstage | Enterprise Shared | OIDC (Authentik) + OpenFGA RBAC Plugin |
| **Universal Registry** | Sonatype Nexus OSS | Enterprise Shared | Authentik LDAP Outpost (Docker, Helm, Maven, NPM, PyPI) |
| **Corporate Mail** | Stalwart Mail Server | Enterprise Shared | Authentik LDAP Outpost / Directory Sync (SMTP, IMAP, JMAP) |
| **Control Plane Storage** | Central MinIO | Enterprise Shared | Internal S3 credentials for Nexus, TechDocs, Stalwart Blobs |
| **Control Plane DB** | Central PostgreSQL 17 | Enterprise Shared | Dedicated databases (`authentik`, `drr_stalwart_mailserver_db`, `openfga`, `backstage`) |
| **CI Engine** | Tekton Pipelines | Enterprise Shared | K8s RBAC + Workload Identity |
| **CD / GitOps** | ArgoCD | Enterprise Shared | Authentik OIDC SSO |
| **Master PKI / Vault** | OpenBao Master | `secr-internal` | Root/Intermediate CA & SPIRE Master Keys |
| **Dynamic Secrets** | OpenBao Tenant Engine | Tenant Environment | SPIFFE Auth Method (Zero Static Tokens) |
| **Edge API Gateway** | Apache APISIX | Tenant Environment | mTLS termination + OpenFGA Plugin |
| **Central Platform IAM** | Keycloak Platform | Enterprise Shared | Federated with Authentik Master Directory (Upstream OIDC Brokering) |
| **Tenant Application IAM** | Keycloak Tenant Instance | Tenant Environment | Dedicated per-tenant Keycloak managing business application users |
| **Tenant Object Storage** | Tenant MinIO / Buckets | Tenant Environment | S3 API + Tenant IAM Policies |
| **Tenant Relational DB** | PostgreSQL | Tenant Environment | CloudNative-PG Operator |
| **Tenant NoSQL DB** | MongoDB | Tenant Environment | MongoDB Community Operator |
| **Streaming Broker** | Apache Kafka | Tenant Environment | Strimzi Operator |
| **Messaging Broker** | RabbitMQ | Tenant Environment | RabbitMQ Topology Operator |
| **APM & Tracing** | SigNoz + OpenTelemetry | Enterprise Shared | OTel Collector with Tenant Tag Injection |
| **Network & Security** | Cilium CNI + WireGuard| Platform-wide | eBPF L3-L7 Policies & Transparent Encryption |

---

## 6. Fine-Grained Authorization Model (OpenFGA)

The platform applies Relationship-Based Access Control (ReBAC) structured across the hierarchy:
$$\text{Tenant} \longrightarrow \text{Project} \longrightarrow \text{Environment} \longrightarrow \text{Component}$$

### `authz/schema.fga` (DSL v1.2)

```dsl
model
  schema 1.1

type user

type tenant
  relations
    define admin: [user]
    define member: [user] or admin

type project
  relations
    define tenant: [tenant]
    define owner: [user] or admin from tenant
    define maintainer: [user] or owner
    define viewer: [user] or maintainer or member from tenant

    define can_create_environment: maintainer
    define can_delete: owner

type environment
  relations
    define project: [project]
    
    define operator: [user] or maintainer from project
    define deployer: [user] or operator
    define viewer: [user] or deployer or viewer from project

    define can_deploy: deployer
    define can_view_logs: viewer
    define can_manage_secrets: operator
    define can_destroy_env: owner from project

type component
  relations
    define environment: [environment]
    define maintainer: [user] or operator from environment
    define viewer: [user] or viewer from environment

    define can_read: viewer
    define can_write: maintainer
    define can_restart: maintainer

```

## 7. Multi-Tenancy & Zero Trust Workload Workflow

### Namespace Isolation Pattern: drr-tnt-{tenant_id}-{project_id}-{environment}.

### Workload Identity Lifecycle:

- The Pod starts in MicroK8s with a dedicated ServiceAccount.

- The SPIRE Agent daemonset attests the Pod using the Kubernetes Workload Attestor.

- SPIRE issues an X.509 SVID with URI: 

`spiffe://darueira.local/ns/{namespace}/sa/{serviceaccount}.`

### Dynamic Secret Retrieval:

- The application uses its SVID certificate to authenticate against OpenBao via the SPIFFE Auth Method.

- OpenBao verifies the SPIFFE ID, applies the matching tenant access policy, and issues short-lived database/broker credentials directly into memory (via CSI Driver).

### CI/CD Lifecycle:

- Developer triggers pipeline via Backstage / drr-ctlr-cli.

- Tekton PipelineRun builds, tests, runs security scans (Trivy), and pushes artifacts to Nexus OSS (with blobs persisted in Central MinIO).

- ArgoCD syncs the target environment manifest into the tenant namespace.

## 8. OPA Sidecar & Hybrid Policy Enforcement Engine

### 8.1. Architecture & PEP / PDP Separation
The platform enforces a strict separation between the **Policy Enforcement Point (PEP)** and the **Policy Decision Point (PDP)** within workload Pods:
- **PEP (Envoy Proxy)**: Intercepts all inbound HTTP/gRPC traffic at the Pod network boundary on listener port `8000`. It utilizes the standard `envoy.filters.http.ext_authz` extension to delegate authorization decisions to OPA before routing to the application container.
- **PDP (Open Policy Agent - OPA)**: Listens on local loopback gRPC (`127.0.0.1:9191`) and HTTP (`127.0.0.1:8181`). It evaluates contextual attributes, SPIFFE IDs, claims, and Rego policy rules, querying OpenFGA (`drr-iam-authz-svc`) when relationship graph checks are required.

### 8.2. Envoy Proxy `ext_authz` Filter Specification
- **Filter**: `envoy.filters.http.ext_authz` (Transport API v3).
- **Interception Flow**:
  $$\text{Ingress Traffic} \longrightarrow \text{Envoy PEP (:8000)} \xrightarrow[\text{timeout: 0.25s}]{\text{gRPC :9191}} \text{OPA PDP} \xrightarrow[\text{ReBAC}]{\text{Graph Check}} \text{OpenFGA} \longrightarrow \text{App (:8080)}$$
- **Timeout Limit**: Strict timeout threshold of `0.25s` (250ms) for gRPC check calls to prevent connection bottlenecks.
- **Fail-Closed Security**: `failure_mode_allow: false` is strictly enforced. If OPA is unreachable, booting, or times out, Envoy rejects the incoming request with HTTP `503 Service Unavailable`.
- **Payload Inspection**: Up to `8192` bytes (8 KB) of request body can be buffered and forwarded to OPA for attribute-based and body-content validation.

### 8.3. Authorization Enforcement Scope
The platform applies differentiated authorization enforcement across service types:

| Target Domain | Enforcement Architecture | Mechanism |
| :--- | :--- | :--- |
| **Custom Platform Services** (`drr-tenant-svc`, `drr-iam-authz-svc`, `drr-env-orchestrator-svc`) | **Full In-Pod Sidecar (PEP + PDP)** | Envoy `ext_authz` sidecar + OPA sidecar (`workload-sidecar-patch.yaml`) |
| **Tenant Workload Pods** (`drr-tnt-{tenant}-{project}-{env}`) | **Full In-Pod Sidecar (PEP + PDP)** | Envoy `ext_authz` sidecar + OPA sidecar (`workload-sidecar-patch.yaml`) |
| **COTS Enterprise Shared Services** (Nexus, Stalwart, MinIO, OpenBao, Authentik) | **Edge & Network Boundary Enforcement** | Apache APISIX Ingress Gateway + OpenFGA Plugin + Cilium L7 NetworkPolicies |

### 8.4. Rego Policy Distribution & Dynamic Updates
- **Bundle Storage**: Rego policies (`.rego`) and static data are stored in a dedicated bucket inside Central MinIO (`s3://drr-policy-bundles/`).
- **Distribution**: OPA sidecars pull bundles periodically or receive push notifications via webhook on policy update.
- **Policy Revocation**: Immediate bundle invalidation through ETag checks and cache eviction.

### 8.5. OpenFGA Tuple Synchronization & Revocation
- **Event-Driven Mutations**: Tenant/Project/Environment lifecycle events publish tuple mutation messages to Kafka topic `drr.authz.tuple-events`.
- **Reconciliation Engine**: `drr-iam-authz-svc` consumes events, writes/deletes tuples in OpenFGA PostgreSQL backend, and invalidates local evaluation caches.

---

## 9. Enterprise Observability Stack (`drr-corpshared-obs`)

The observability tier provides 360-degree Zero Trust observability across metrics, logs, distributed traces, and security audits:

```mermaid
graph TD
    WorkloadPod["Tenant / Platform Pod\n(App + Envoy PEP + OPA PDP + OTEL Agent)"] -->|OTLP gRPC :4317 / HTTP :4318| OTEL["OpenTelemetry Collector\n(drr-corpshared-obs)"]
    
    OTEL -->|Metrics| Prometheus["Prometheus Server\n(drr-corpshared-obs)"]
    OTEL -->|Traces| Jaeger["Jaeger Tracing Backend\n(drr-corpshared-obs)"]
    OTEL -->|Logs & Audits| OpenSearch["OpenSearch Cluster\n(drr-corpshared-obs)"]
    
    Prometheus --> Grafana["Grafana Dashboards\n(drr-corpshared-obs)"]
    Jaeger --> Grafana
    OpenSearch --> Grafana
    
    Backstage["Backstage IDP\n(drr-corpshared-mgmt)"] -->|Plugin Views| Grafana
```

### 9.1. Core Observability Components:
1. **OpenTelemetry Collector (`otel-collector`)**:
   - Central ingestion gateway for OpenTelemetry Protocol (OTLP).
   - Ingests OTLP traces (`grpc:4317`, `http:4318`), metrics, and structured logs.
   - Dispatches signals to Prometheus, Jaeger, and OpenSearch with batching and memory limiting.
2. **Prometheus Engine (`prometheus`)**:
   - Time-series metrics engine scraping Kubernetes nodes, control plane components, and tenant pods.
   - Alertmanager integration for infrastructure threshold breaches.
3. **Jaeger Tracing (`jaeger`)**:
   - Distributed tracing backend recording spans across Envoy PEP, OPA PDP, `drr-iam-authz-svc`, and backend business APIs.
4. **OpenSearch Cluster (`opensearch`)**:
   - Centralized distributed log search, indexing, and SIEM security analytics.
5. **Grafana Visualization (`grafana`)**:
   - Centralized visualization platform providing unified dashboards for infrastructure, security policies, and tenant applications.

### 9.2. In-Pod OTEL Auto-Instrumentation
All platform and tenant pods export telemetry via standard OTLP environment variables:
- `OTEL_EXPORTER_OTLP_ENDPOINT`: `http://otel-collector.drr-corpshared-obs.svc.cluster.local:4317`
- `OTEL_EXPORTER_OTLP_PROTOCOL`: `grpc`
- `OTEL_SERVICE_NAME`: `{service-name}`
- `OTEL_RESOURCE_ATTRIBUTES`: `k8s.namespace.name={namespace},k8s.pod.name={pod_name},darueira.io/tenant={tenant_id}`

---

## 10. Enterprise PKI, Identity & Messaging Infrastructure

### 10.1. Certificate Management & PKI (`cert-manager`)
- Namespace: `drr-corpshared-secr-internal`.
- Automates X.509 certificate issuance and rotation across Ingress routes and internal service endpoints.
- Provides `ClusterIssuer` definitions backed by OpenBao (Vault PKI engine) and internal Root CA.

### 10.2. Enterprise Identity Provider (Keycloak / Authentik)
- Namespace: `drr-corpshared-plat`.
- Centralized OIDC / OAuth2 authentication, SAML federation, and multi-tenant realm isolation.
- Backed by Central PostgreSQL 17 for realm configurations and user directories.

### 10.3. Cloud-Native Message Broker (Kafka / Redpanda)
- Namespace: `drr-corpshared-plat`.
- High-throughput, distributed event streaming platform for:
  - `drr.authz.tuple-events`: Event-driven ReBAC tuple mutations;
  - `drr.tenant.lifecycle-events`: Tenant, Project, and Environment provisioning events;
  - `drr.audit.security-events`: Zero Trust security and policy enforcement audit trails.