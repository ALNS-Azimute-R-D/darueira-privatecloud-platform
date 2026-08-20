# ADR 0013: Multi-Tenant Infrastructure Topology, Shared Environment Hierarchy, and Isolated Storage Conventions

## Status
Accepted

## Context
In the Darueira Private Cloud Platform, tenant isolation, compute resources, and data storage must follow strict architectural standards to ensure zero-trust boundaries, operational simplicity, and multi-tenant resource hygiene.

Previous iterations generated namespaces tied to individual projects (e.g. `drr-tnt-{tenant}-{project}-{env}`), which introduced unnecessary infrastructure fragmentation, duplicated tenant services, and risked unintended shared-services coupling (e.g. storing tenant business data in Central PostgreSQL).

To standardize tenant topologies and prevent data cross-contamination:
1. Namespace hierarchy must reflect the Tenant and Environment boundary, not individual projects.
2. All projects within a Tenant must share the tenant's environments (`dev`, `stg`, `prd`).
3. Each tenant environment must host its own isolated baseline infrastructure services.
4. Tenant workloads must never store data in Central Corporate Shared Services.

## Decision

### 1. Tenant Environment & Namespace Naming Standard
- Every Tenant is initialized with a default `dev` environment. Subsequent environments (`stg`, `prd`) are provisioned on-demand.
- Kubernetes namespaces follow the strict format:
  $$\text{Namespace} = \mathbf{\text{drr-tnt-}<\text{Tenant Name}>-<\text{Environment}>}$$
  *(e.g., `drr-tnt-swfabrik-europe-dev`, `drr-tnt-swfabrik-europe-prd`, `drr-tnt-acme-dev`)*.
- **Rule**: A Tenant can have 1 or more Projects. All Projects belonging to a Tenant share the same Environments of that Tenant. **Never create an exclusive Environment or Namespace per Project.**

### 2. Dedicated Baseline Services per Tenant Environment
Each `drr-tnt-<tenant>-<env>` namespace possesses its own dedicated, isolated installation of essential data and security services:
- **OpenBao (`tenant-openbao`)**: Dedicated tenant secrets management, KV store, and transit encryption.
- **MinIO (`tenant-minio`)**: Dedicated tenant S3-compatible object storage.
- **PostgreSQL (`tenant-postgres`)**: Dedicated relational database server.
- **MongoDB (`tenant-mongodb`)**: Dedicated document database server.
- **Keycloak (`tenant-keycloak`)**: Dedicated tenant identity provider and user realm.

### 3. Data Storage & Schema Isolation Conventions
- **Strict Prohibition**: Tenant projects/workloads must **NEVER** store data or files in Corporate Shared Services (`drr-corpshared-*`). All persistence must target the local tenant environment services (`tenant-postgres`, `tenant-mongodb`, `tenant-minio`).
- **PostgreSQL Database Conventions**:
  Every `tenant-postgres` instance must contain two standard databases:
  1. `drr_tnt_keycloak_db`: Exclusively for Tenant Keycloak metadata.
  2. `drr_tnt_bizapps_db`: For all tenant business applications and project workloads.
- **Schema Separation for Projects**:
  Each Project requiring relational persistence in `drr_tnt_bizapps_db` is allocated an isolated schema following the sequential standard:
  $$\mathbf{\text{schm}<\text{sequential number}>} \quad (\text{e.g., } \text{schm01}, \text{schm02}, \dots, \text{schm06})$$

## Consequences
- **Strict Data Isolation**: Tenant business data is completely segregated from platform control plane databases and from other tenants.
- **Cost & Resource Efficiency**: Projects within the same tenant reuse the tenant's dedicated databases and services without spawning redundant daemon overhead per project.
- **Predictable Infrastructure**: Uniform naming, zero-trust policies, and schema conventions streamline GitOps automation, CI/CD pipelines, and observability.
