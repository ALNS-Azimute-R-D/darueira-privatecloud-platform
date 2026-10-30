# PingFederate to Keycloak Migration Lab (Missão Ninja 2 / Volvo): Tests, Demos and Customization

## From Andre:

On 23.10.2026, André asked both Claude and Antigravity to implement **tests and demos that simulate a
PingFederate to Keycloak migration**, using new Keycloak features and customizing it. This prepares the second
"Missão Ninja": an interview (not yet scheduled) for an IAM/Keycloak specialist role on a large-scale
PingFederate to Keycloak migration at Volvo. André will pass details later; do not assume interview date,
format or scope.

Collaborative format: each agent writes only its own sections, then debate and a joint final decision.
The Keycloak version rollout (26.8.1) is covered in `keycloak-upgrade-26.8.1.md` and is a prerequisite to check.

---

## Analysis and Evaluation by Claude:

### 1. What exists in the lab (verified by listing; details still to confirm)

- Platform: central `keycloak-server` (`drr-corpshared-plat`) federated with Authentik, and one
  `tenant-keycloak` per tenant (europe-dev, latam-dev), each backed by Postgres. Make targets already exist:
  `bootstrap-tenant-keycloak`, `validate-iam`, `bootstrap-iam`, `bootstrap-openfga`.
- Reference material on disk: `.../IAM-Security/Keycloak-Stuff` (dasniko, thomasdarimont, phasetwo.io,
  keycloak-extensions, KeyCloak-MultiTenancy, ...), `.../IAM-Security/clavex-iam`.
- There is **no PingFederate** here. The legacy IdP must be simulated.

### 2. What a real PingFederate to Keycloak migration involves (to be checked against current docs)

| Area | PingFederate | Keycloak target | Lab simulation |
|---|---|---|---|
| Users and passwords | LDAP / data stores, legacy hashes | User Storage SPI or federation; lazy migration on first login; custom credential provider for legacy hashes | stub store with legacy-hashed users |
| SP connections (SAML) | SP connections, attribute contracts | SAML clients, mappers, signing/encryption config | metadata import of a sample SP |
| OIDC/OAuth clients | OAuth clients, access token managers, scopes | OIDC clients, client scopes, protocol mappers | client export/import script |
| Adapters / policies | authentication policies, selectors, adapters | authentication flows, conditional flows, required actions | recreate a policy as a custom flow |
| Token contents | OGNL expressions in contracts | protocol mappers / script-less custom mapper SPI | custom mapper producing legacy claim names |
| Sessions / cutover | per-app cutover | coexistence via identity brokering, phased by application | broker legacy IdP, migrate app by app |

### 3. Proposed lab (open for debate)

1. **Legacy IdP stub**: a minimal SAML/OIDC IdP (container) exposing PingFederate-like behavior and legacy
   attribute names, with a seed user set including legacy password hashes.
2. **Migration tooling**: scripts that read legacy config (users, SP/OIDC clients) and generate a Keycloak realm
   (JSON import or Admin API / `kcadm`), idempotent.
3. **Customization**: a Keycloak extension (Java/Kotlin SPI) for lazy credential migration and a protocol mapper
   reproducing legacy claims; built against the Keycloak version the cluster runs.
4. **Strategies demo**: (a) big-bang import, (b) lazy migration on login, (c) brokering both IdPs during phased
   cutover, with the trade-offs of each.
5. **Automated tests**: Testcontainers (Keycloak + stub) for the SPI, plus black-box `make validate-pf-migration`
   asserting login, claims parity (legacy vs new token) and account-linking, in the style of `validate-iam`.
6. **New Keycloak features**: to select after reading the 26.7/26.8 release notes (do not assume).

### 4. Risks and open questions (Claude)

- Keep it clear what is real vs simulated in any demo: PingFederate is not installed, only a stub.
- Which migration scale/metrics does the role emphasize (users, apps, downtime)? Unknown until André has details.
- Run against a throwaway realm or a dedicated Keycloak, not the realms that Backstage/Forgejo/ArgoCD use.
- Where does the code live: a new directory under `workspace/` or `apps/`, or a separate repo for the portfolio?

---

## Analysis and Evaluation by Antigravity:

_(to be filled by Antigravity: second view on the lab design, PingFederate specifics, Keycloak features, risks)_

---

# Discussion/Debate:

## Highlighted points from Antigravity's analysis:

_(pending)_

## Highlighted points from Claude's analysis:

_(pending)_

## Counterpoints and clarifications from Antigravity:

_(pending)_

## Counterpoints and clarifications from Claude:

_(pending)_

---

# Final Decisions After Both Agreement and Disagreement:

_(pending)_

# Action Plan for the Migration Lab:

_(pending: phases, owner per item, which realm/cluster is touched, single-writer rule)_
