# ADR 0002: ReBAC Fine-Grained Authorization with OpenFGA

## Status
Accepted

## Context
Multi-tenant platform engineering requires fine-grained authorization across a deep hierarchy:
Tenant -> Project -> Environment -> Component.
Traditional RBAC alone struggles with transitive inheritance and resource-level relationship boundaries (e.g., Tenant Admin inheriting full control over all child projects/environments, while Environment Deployers are restricted from secret management or environment deletion).

## Decision
Adopt OpenFGA (Relationship-Based Access Control - ReBAC) based on Google Zanzibar principles.
The schema is defined in DSL v1.2 (`authz/schema.fga`) and validated through automated unit test suites (`authz/tests.fga.yaml`).

## Consequences
- Clean separation between coarse-grained authentication (Authentik / Keycloak OIDC) and fine-grained authorization (OpenFGA).
- Fast in-memory relationship graph evaluation with sub-millisecond check latency.
- Deterministic automated testing of authorization rules before deploying changes.
