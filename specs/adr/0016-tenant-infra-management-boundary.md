# ADR 0016: Architectural Boundary for Tenant Infrastructure Management — Platform Control Plane vs. Tenant GitOps

## Status
Accepted

## Context
In the Darueira Private Cloud Platform, tenant isolation and deployment mechanisms were initially split across two different paradigms:
1. **Central Platform Services** (`drr-corpshared-*`): Managed declaratively in the platform repository (`platform/kustomize/base/corpshared-*`) and orchestrated via Makefile targets and platform automation.
2. **Tenant Common Infrastructure** (`tenant-keycloak`, `tenant-postgres`, `tenant-minio`, `tenant-mongodb`, `tenant-openbao`, `tenant-mysql`): Initially deployed through tenant-owned Git repositories (`<tenant>/infra-k8s.git`) synchronized by ArgoCD Applications (`swfabrik-*-tenant-infra`) configured with `selfHeal: true`.

During operational maintenance, upgrades (e.g., Keycloak 26.8.1, production mode transition `kc.sh start`), and probe tuning, this dual model presented critical operational and architectural friction:
- **N-Repo Sprawl & Divergence**: Maintaining separate `infra-k8s.git` repositories for every tenant led to duplicated manifests and prevented synchronized rollouts of infrastructure bugfixes across tenants.
- **Silent Revert Hazard**: Because ArgoCD monitored `infra-k8s.git` with `selfHeal: true`, platform-level interventions or hotfixes applied directly to tenant namespaces were silently rolled back within seconds by ArgoCD.
- **Muddled Responsibility Boundaries**: Common tenant infrastructure services are PaaS building blocks (databases, object storage, identity providers, secret stores) owned by Platform Engineering, not application-level business code owned by product squads.

The Platform Architect (André Nascimento) clarified the intended architectural boundary: **Tenant GitOps (Forgejo + Tekton + ArgoCD) must be strictly reserved for tenant business applications (SaaS). All foundational infrastructure services—both central corporate and tenant-local—belong to the Platform Control Plane (PaaS).**

## Decision

### 1. Management Boundary Separation
- **Tenant GitOps Scope (SaaS)**:
  - Strictly limited to business application workloads (e.g., `app-food-market-*`, `bookanything-*`, `caseforce-legalhub-*`, `checkout-service`, `app-identity-studio`).
  - Managed via tenant project repositories in Forgejo, built and packaged via Tekton CI, and continuously reconciled by ArgoCD Applications in `platform/gitops/argocd-apps/`.
- **Platform Control Plane Scope (PaaS)**:
  - Encompasses all common platform infrastructure across both corporate namespaces (`drr-corpshared-*`) and tenant namespaces (`drr-tnt-<tenant>-<env>`).
  - Tenant baseline services (`tenant-postgres`, `tenant-mongodb`, `tenant-minio`, `tenant-openbao`, `tenant-keycloak`, `tenant-mysql`) are governed directly in the platform repository under `platform/kustomize/overlays/tenants/<tenant>/` inheriting from `platform/kustomize/base/tnt-tenant-base/`.

### 2. Deployment Tooling & Standard Commands
- Tenant common infrastructure is managed and deployed via dedicated Makefile targets:
  - `make diff-tenant-infra TENANT=<tenant>`: Runs `kubectl diff -k` against the live cluster to verify changes with zero unintended side-effects.
  - `make deploy-tenant-infra TENANT=<tenant>`: Applies the Kustomize overlay to the designated tenant namespace.
- Validation is integrated into the core manifest verification suite:
  - `make validate-manifests`: Now includes validation of all tenant infrastructure overlays (`platform/kustomize/overlays/tenants/*`).

### 3. Safe Cutover & Cascade Protection
- Existing ArgoCD infrastructure Applications (`swfabrik-*-tenant-infra`) are decommissioned without service disruption:
  - Automation (`syncPolicy`) is stripped and `finalizers` confirmed empty.
  - Application deletion is executed with native Kubernetes orphan propagation (`kubectl delete application <name> --cascade=orphan`).
  - Workloads (Pods, StatefulSets, Deployments, PVCs, Secrets) remain 100% online and unperturbed during cutover.
  - ArgoCD tracking labels (`argocd.argoproj.io/instance`) are pruned from tenant infrastructure resources.

### 4. Repository Lifecycle in Forgejo
- Historical tenant `infra-k8s.git` repositories in Forgejo are set to **Archived (read-only)** via the Forgejo REST API.
- Repositories are preserved to retain commit history and audit trails, while preventing accidental commits or GitOps sync conflicts.

### 5. Tenant Baseline Specification Closure
- Added `tenant-mysql.yaml` to `platform/kustomize/base/tnt-tenant-base/` and its `kustomization.yaml`, formally closing the documentation and template gap identified in `specs/01-initial-spec.md` §11.2 item 4.

## Consequences
- **Unified Platform Lifecycle**: Platform engineers can patch CVEs, upgrade database engines, and tune health probes across all tenants simultaneously from a single repository.
- **Zero ArgoCD Drift / Silent Reverts**: Platform control plane operations are authoritative and will not be reverted by ArgoCD background sync loops.
- **Clean DevSecOps Separation**: Application developers and product teams interact with GitOps exclusively for their own microservices without permissions or exposure to core database StatefulSets or tenant identity providers.
- **Safe, Auditable Operations**: All tenant infrastructure changes are subjected to `make diff-tenant-infra` prior to execution, ensuring predictable, non-disruptive deployments.
