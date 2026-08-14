# drr-iam-authz-svc

## Overview
Identity & Authorization Gateway Service for Darueira Private Cloud Platform.

## Responsibilities
- Intercepts API and Ingress traffic to perform fine-grained authorization checks.
- Validates OIDC JWT tokens and claims from Authentik / Keycloak.
- Evaluates Relationship-Based Access Control (ReBAC) tuples against OpenFGA (`authz/schema.fga`).
- Enforces multi-tenant isolation and role-based / relation-based permissions across Tenants, Projects, Environments, and Components.
- Integrates with Apache APISIX as an external authz plugin / forward auth service.

## Tech Stack
- Go Lang / Kotlin
- OpenFGA Go SDK
- SPIFFE/SPIRE Workload Attestation
