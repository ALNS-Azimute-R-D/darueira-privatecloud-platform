# ADR 0022: drr-iam-authz-svc Hardening — Keycloak JWKS Validation and an Internal-Only API

## Status
Accepted (2026-11-23). Refines ADR-0021 and the Zero Trust tenets of `AGY.md` (never expose administrative endpoints without
route policies and OIDC/mTLS validation).

## Context
Writing the first relationship tuples (ADR-0021) exposed three problems in `drr-iam-authz-svc`:
1. **The API is public and unauthenticated.** The APISIX route `route-host-api-authz` forwards `/*` of the service to anyone who reaches
   the gateway, with only the `prometheus` plugin. That includes `POST/DELETE /api/v1/authz/tuples`: any client could grant itself any
   permission. Nothing in the repository consumes that public host; `drr-tenant-svc` and `drr-env-orchestrator-svc` use the in-cluster Service.
2. **Token validation is a no-op.** Without `OIDC_CLIENT_SECRET` (the Deployment has none) the validator runs in a "dev/mock" mode that
   accepts any JWT without checking signature, issuer or expiry. With a secret it only accepts HMAC, while Keycloak signs with RS256.
3. **The tenant claim does not match.** The code reads `tenant_id`; the Keycloak mappers emit `tenant` (user attribute `tenant`).

## Decision
1. **Internal-only API.** The public route exposes only `GET /healthz` and `GET /readyz`. Check, batch-check, tuple mutation and
   forward-auth are reachable only inside the cluster (ClusterIP + Cilium policies). Exposing any of them again needs an ADR that
   defines authentication (OIDC) and, for tuple mutation, an administrator role.
2. **Verified tokens only, fail closed.** Bearer tokens are verified against the realm JWKS (`OIDC_JWKS_URL`, fetched in-cluster, cached
   10 minutes, refreshed at most every 10 s when an unknown `kid` shows up): signature algorithm allow-list `RS256`, issuer equal to
   `OIDC_ISSUER_URL`, `exp` required (30 s leeway), optional audience (`OIDC_AUDIENCE`), a `kid` and a `sub` are mandatory. The dev/mock
   mode is removed: if the issuer or the JWKS URL is not configured, every token is rejected.
3. **Tenant claim.** `tenant_id` if present, otherwise `tenant` (what Keycloak emits today); a string or a one-element list.
4. **Identity in OpenFGA** stays `user:<sub>` (the immutable Keycloak id) and `tenant:<tenant claim>`.

## Consequences
- **Positive:** the permission model can no longer be rewritten or bypassed from outside; tokens must really come from Keycloak.
- **Cost:** no external consumer of the authz API until a new ADR; operators call it with `kubectl port-forward` or from in-cluster pods.
- **Risk:** Keycloak key rotation is handled by the JWKS refresh; if Keycloak is down at startup, tokens are rejected until it is reachable
  (fail-closed, visible as `error` decisions in the alerts of backlog item 48).
- **Not covered:** the OIDC plugin of other APISIX routes still carries a literal client secret in `bootstrap_apisix_routes.py`
  (backlog); the service-to-service calls to this API are not yet authenticated (SPIFFE/mTLS tenet).
