# 7. Tiered Identity Architecture: Authentik Directory, Central Keycloak Federation, and Tenant IAM Isolation

Date: 2026-08-17

## Status

Accepted

## Context

The Darueira Private Cloud Platform serves two distinct user personas and workload domains with very different governance, lifecycle, and security isolation requirements:
1. **Enterprise & Platform Personas**:
   - Internal employees, platform engineers, operators, and external business partners requiring access to core infrastructure consoles (APISIX, Vault, Backstage, OpenSearch, Grafana, ArgoCD, Tekton) and communication services (Corporate Mail Server).
   - Requires a centralized, authoritative Enterprise Directory (LDAP/Directory) and single source of truth for identity lifecycle, MFA, and organizational group memberships.
2. **Tenant End-Users & Business Applications**:
   - End-users of multi-tenant business applications running inside tenant environments (e.g. `drr-tnt-acme-storefront-dev`).
   - Must be strictly isolated between tenants to prevent data contamination, cross-tenant privilege escalation, and noisy-neighbor issues.
   - Tenants require autonomy over user self-registration, client credentials, custom realms, and tenant-specific login theming without impacting platform control plane identity.

## Decision

We establish a **Tiered Identity & Directory Architecture** with strict segregation of duties:

```
+-----------------------------------------------------------------------------------+
|               ENTERPRISE SOURCE OF TRUTH: Authentik Directory (LDAP)              |
|        (Internal Staff, Platform Engineers, Operators, Business Partners)        |
+-----------------------------------------+-----------------------------------------+
                                          |
                +-------------------------+-------------------------+
                |                                                   |
                v                                                   v
+-----------------------------------+             +-----------------------------------+
|       Stalwart Mail Server        |             |      Central Platform Keycloak    |
|   (Authentik LDAP/Directory Sync) |             | (Federated with Authentik OIDC)   |
|   - Corporate Mailboxes           |             | - Backstage, ArgoCD, Vault SSO    |
|   - IMAP/SMTP/JMAP Authentication |             | - Platform Admin & Mgmt Realms    |
+-----------------------------------+             +-----------------------------------+

============================= TRUST BOUNDARY SEPARATION =============================

+-----------------------------------------------------------------------------------+
|               TENANT APPLICATION LAYER: Dedicated Tenant Keycloaks                |
|                    (drr-tnt-{tenant}-{project}-{env})                             |
+-----------------------------------------------------------------------------------+
| - Tenant Acme Keycloak        | - Tenant Beta Keycloak      | - Tenant Gamma Keycloak     |
|   - Storefront Customers      |   - Mobile App Users        |   - B2B API Clients         |
|   - Independent User DB       |   - Independent User DB     |   - Independent User DB     |
+-------------------------------+-----------------------------+---------------------+
```

1. **Authentik as the Central Enterprise Directory & Source of Truth**:
   - **Authentik** (`drr-corpshared-plat`) acts as the primary Enterprise Identity Provider and LDAP Outpost/Directory.
   - All internal organizational accounts, platform engineers, corporate email owners, and certified partner credentials reside in Authentik.

2. **Corporate Mail Server (Stalwart) Directory Integration**:
   - **Stalwart Mail Server** is configured to consume **Authentik Directory (LDAP / Directory Provider)** as its primary user directory.
   - Mailbox creation, aliases, group distribution lists, and IMAP/SMTP credentials synchronize against Authentik, ensuring single-source lifecycle deprovisioning.

3. **Central Platform Keycloak Federation**:
   - The **Central Platform Keycloak** (`drr-corpshared-plat`) federates with **Authentik** as its upstream Identity Provider (via OIDC / SAML identity brokering).
   - Platform developer consoles (Backstage, Grafana, OpenSearch Dashboards, ArgoCD) authenticate via Keycloak, which delegates user authentication upstream to Authentik.

4. **Dedicated Per-Tenant Keycloak Isolation**:
   - End-users of business applications are **NEVER** stored in the Central Authentik Directory or the Central Platform Keycloak.
   - Every provisioned tenant environment (`drr-tnt-{tenant}-{project}-{env}`) receives its own isolated Keycloak deployment backed by tenant-scoped persistence.
   - Tenant administrators have full autonomy over their application realms, client registrations, and user lifecycles without access to corporate directories or other tenants' data.

## Consequences

- **Clear Separation of Concerns**: Enterprise corporate identities remain strictly isolated from customer/consumer accounts of tenant applications.
- **Unified Employee Lifecycle**: Deprovisioning an employee or partner in Authentik automatically revokes access across email (Stalwart), platform consoles (Backstage/ArgoCD/Vault), and infrastructure tools.
- **Tenant Autonomy & Multi-Tenancy Compliance**: Tenant applications can customize authentication flows, password policies, and OAuth2 scopes independently without cross-tenant blast radius.
- **Zero Cross-Contamination**: Breach of a tenant application's user database cannot compromise corporate platform infrastructure or other tenants.
