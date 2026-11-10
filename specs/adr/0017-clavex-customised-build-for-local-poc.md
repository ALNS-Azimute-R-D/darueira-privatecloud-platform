# ADR 0017: Customised Clavex build (community org limit override) for local PoC

## Status
Accepted (local lab / PoC only)

## Context
Clavex (eIDAS 2.0 / EUDI IAM, `clavex-eu/clavex`) is licensed under BSL 1.1. The community edition is
limited to **one organisation**; its Additional Use Grant states that local development, staging,
testing and CI use is always permitted and does not count against that limit, while production use with
2+ organisations needs a commercial license. The Token Exchange / EUDI Wallet / IdP-integration PoC
needs three organisations (`swfabrik-europe`, `swfabrik-latam`, `acme-logistics`).

## Decision
1. Patch the upstream source on branch `alns-darueira-customizations` (commit `1b78839`): the
   community org limit is read from `CLAVEX_LICENSE_COMMUNITY_ORG_LIMIT` (default 1, invalid values
   ignored, a warning is logged when overridden). License JWT verification is untouched.
2. Build and store the images in the platform Nexus:
   `127.0.0.1:32082/darueira-corpshared/clavex:1.8.2-lab1` and `clavex-ui:1.8.2-lab1`.
3. Deploy with the Helm chart in Forgejo `darueira-corp/clavex-darueira-chart` (release `clavex`,
   namespace `drr-corpshared-plat`, `communityOrgLimit: 10`). Clavex is `drr-corpshared-*` PaaS
   (ADR-0016): **not** ArgoCD; deployed with `helm upgrade --install`. The platform repo keeps only
   the Secret `clavex-secrets` (`platform/kustomize/base/corpshared-plat/clavex.yaml`).
4. Database: `drr_clavex_db` (owner `clavex`) on `central-postgres`, namespace `drr-corpshared-plat`.

## Consequences
- Strictly local/PoC: this build must not serve real users with 2+ organisations (BSL 1.1). Keep the
  upstream `LICENSE` with the modified source and do not redistribute the image publicly.
- The patch must be re-applied (rebased) when upgrading the upstream version.
- Clavex has a usage-reporting worker (`telemetry.clavex.eu`); it currently fails TLS verification
  in the lab. Decide explicitly whether to disable it.
- `clavex-secrets` still holds plaintext values in git (backlog #1): move to OpenBao.
