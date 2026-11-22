# ADR 0021: OpenFGA on a Persistent Datastore and Store/Model Provisioning from `authz/schema.fga`

## Status
Accepted (2026-11-22). Refines the OpenFGA ReBAC engine of `specs/01-initial-spec.md`; depends on the system PostgreSQL of the
control plane (`central-postgres`, ADR-0011).

## Context
The metrics added to `drr-iam-authz-svc` (backlog item 46) showed every authorization check failing with HTTP 500. Root cause:
- OpenFGA runs with `OPENFGA_DATASTORE_ENGINE=memory`, so **every restart erases all stores, models and tuples** (the pod has
  restarted 109 times); the store and model ids hard-coded in `iam-authz-svc.yaml` pointed to objects that no longer existed;
- the bootstrap script `scripts/bootstrap_openfga_rebac.py` embeds an older model (`organization`/`project`/`environment`) with
  demo tuples for tenants that no longer exist (ACME, Globex), while the source of truth required by the SDD rules is
  `authz/schema.fga` (`tenant`/`project`/`environment`/`component`), which is what `drr-tenant-svc` (tuples `tenant:<id>`) targets.

## Decision
1. **Persistence.** OpenFGA uses PostgreSQL (`OPENFGA_DATASTORE_ENGINE=postgres`) on `central-postgres`, in its own database
   `drr_openfga_db`, owned by the least-privilege role `openfga_app` (no superuser, no CREATEDB/CREATEROLE). The role, the database and the
   Secret `openfga-db` (key `uri`) are created by the idempotent `scripts/provision_openfga_db.sh`; the password is generated in
   memory and never reaches Git. An init container runs `openfga migrate` before the server starts.
2. **Model from the source of truth.** `scripts/bootstrap_openfga_rebac.py` converts `authz/schema.fga` to the JSON model
   (`fga model transform`, run from the official `openfga/cli` image), creates the store `darueira-rebac-store` if it does not exist
   and writes a new authorization model only when it differs from the latest one. The embedded model and demo tuples are removed.
3. **Ids are not literals.** The script records `store-id` and `model-id` in the ConfigMap `openfga-ids` (namespace
   `drr-corpshared-plat`); `drr-iam-authz-svc` reads them with `configMapKeyRef` and the script restarts it when they change.
4. **No invented permissions.** The bootstrap creates the store and the model only. Relationship tuples are written by the
   platform itself (`drr-tenant-svc` writes `user:<id> admin tenant:<id>` when a tenant is created). Seeding tuples for existing
   tenants is a separate, explicit decision of the platform owner.
5. **Validation.** `fga model test` runs `authz/tests.fga.yaml` against the provisioned engine (it uses throw-away stores).

## Consequences
- **Positive:** the engine survives restarts; the model in the cluster is exactly the reviewed `schema.fga`; no ids in Git.
- **Cost:** one more database and a Secret on `central-postgres`, a few MB of storage, and OpenFGA now depends on PostgreSQL being up.
- **Risk:** until tuples exist, checks return `denied` (not `error`): correct fail-closed behaviour. `scripts/validate_openfga_rebac.py` and
  the old seed target the removed demo model and are no longer valid; `fga model test` replaces them.
- **Rollback:** switch the engine back to `memory` and remove the init container (data is lost on restart, as before).
