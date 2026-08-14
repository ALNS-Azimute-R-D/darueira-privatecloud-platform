# drr-tenant-svc

## Overview
Tenant & Project Lifecycle Management Service for the Darueira Private Cloud Platform.

## Responsibilities
- Organization / Tenant lifecycle management (create, update, suspend, delete).
- Project and workspace registry within tenants.
- Tenant resource quotas, rate limits, and membership tracking.
- Syncs tenant and project state with OpenFGA ReBAC tuples and enterprise identity provider (Authentik).

## Architecture & Tech Stack
- **Languages/Frameworks**: Java 25 / Spring Boot 4.1.0 / Kotlin or Go
- **Pattern**: Hexagonal Architecture (Domain, Application Ports, Infrastructure Adapters)
- **Persistence**: Central PostgreSQL (`drr_tenant_db`)
- **Security**: Workload Identity (SPIFFE/SPIRE), OpenFGA authorization client.
