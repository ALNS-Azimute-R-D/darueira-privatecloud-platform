# 9. Internal Git Repository Service: Forgejo for Private Cloud & Local CI/CD

Date: 2026-08-17

## Status

Accepted

## Context

The Darueira Private Cloud Platform requires a self-hosted, lightweight, and robust Git repository server in the Enterprise Shared Services plane (`drr-corpshared-plat`):
1. **Air-Gapped & Offline CI/CD Autonomy**: Enable Tekton Pipelines and ArgoCD GitOps to clone, push, and reconcile tenant and platform repositories locally without relying on external SaaS availability (GitHub.com / GitLab.com).
2. **In-Cluster Webhook Delivery**: Webhooks triggered by `git push` must reach internal Tekton EventListeners (`http://el-tenant-pipeline.drr-corpshared-mgmt.svc.cluster.local:8080`) over cluster DNS without requiring reverse tunnels (e.g. ngrok / Cloudflare Tunnel) to penetrate residential NAT.
3. **Automated Scaffolding via Backstage**: Enable Spotify Backstage Software Templates (Golden Paths) to provision and publish new service code repositories directly via a local REST API.
4. **Minimal Resource Overhead**: Must operate comfortably within developer laptop constraints (< 150 MB RAM, < 0.1 vCPU).

## Decision

1. **Adopting Forgejo (`codeberg.org/forgejo/forgejo:10`)**:
   - Deploy **Forgejo** (open-source, community-driven fork of Gitea) as the primary internal Git server under deployment `forgejo-git` in `drr-corpshared-plat`.
   - Written in native Go, providing full Git over HTTP and SSH (`:2222`), rich web UI, pull requests, issue tracking, access tokens, and GitHub-compatible REST APIs.

2. **Central PostgreSQL Persistence**:
   - Persist metadata, accounts, organizations, pull requests, and webhooks in **Central PostgreSQL** (`central-postgres.drr-corpshared-plat.svc.cluster.local:5432`) under the dedicated database `drr_git_db`.
   - Attach a `PersistentVolumeClaim` (`forgejo-git-pvc`, 5Gi) to `/data` for bare Git repositories and LFS objects.

3. **Kubernetes Security & Network Isolation**:
   - Run as non-root UID `1000` (`git`), `runAsGroup: 1000`, `fsGroup: 1000` under Kubernetes `restricted` Pod Security Standards.
   - Authorize ingress ports `3000` (Web UI/HTTP Git) and `2222` (SSH Git) in `CiliumNetworkPolicy` (`default-deny-and-plat-rules`).
   - Configure `FORGEJO__webhook__ALLOWED_HOST_LIST="*"` to allow direct webhook calls to internal cluster services (Tekton).

4. **Edge Ingress Routing via Apache APISIX**:
   - Expose Forgejo Web UI and HTTP Git via APISIX route `route-host-forgejo` at `https://git.darueira-corpshared.127.0.0.1.nip.io` (and alias `forgejo.*`).

5. **Identity Federation via Keycloak Central OIDC**:
   - Integrate Forgejo authentication with **Keycloak Central IdP** (`darueira-platform-svcs` realm) via OAuth2/OpenID Connect (`keycloak-oidc`).
   - Standardize single sign-on (SSO) with corporate tokens, RBAC administrator group mappings (`drr-platform-admins`), and tenant attribute claims.

6. **Hybrid Push/Pull Mirroring Support**:
   - Allow internal repositories to optionally configure automated Git Push Mirroring to remote GitHub/GitLab accounts for off-site backup.

## Consequences

- **High Speed & Low Resource Footprint**: Provides enterprise Git features with ~80-120 MB RAM footprint, avoiding heavy alternatives like GitLab CE.
- **Zero-Friction CI Triggers**: Instant webhook delivery from Forgejo to Tekton EventListeners without external networking dependencies.
- **Backstage Integration**: Streamlines IDP project generation with local credentials.
