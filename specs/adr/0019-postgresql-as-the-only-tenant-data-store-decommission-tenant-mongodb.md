# ADR 0019: PostgreSQL as the Only Tenant Data Store — Decommission `tenant-mongodb`

## Status
Accepted (2026-11-22). Extends ADR-0018 (which removed `tenant-mysql`) and amends ADR-0013 and ADR-0016, which listed
`tenant-mongodb` in the tenant baseline.

## Context
Every tenant environment received a `tenant-mongodb` StatefulSet. Nothing uses it:
- no workload in any namespace references it (checked in the cluster and in the application code of
  `apps/` and `workspace/platf-bizz-apps/`; the only mention is the `apps/examples/tenant-xpto` template);
- both live StatefulSets (`swfabrik-europe`, `swfabrik-latam`) have run with 0 replicas, and their data directories on the
  host are empty (the data was lost in the 2026-11-08 host disk failure and never recreated);
- it carried a known cost: a heavy `mongosh` probe (backlog item 23) and one more volume competing for the same disk
  (`docs/runbooks/host-disk-io-contention.md`).

As with MySQL (ADR-0018), a second engine per tenant adds upgrades, backups, volumes, policies, credentials and
documentation for no functional gain. PostgreSQL already covers the cases that usually justify a document store.

## Decision

### 1. One data store per tenant: PostgreSQL
`tenant-postgres` is the only database of a tenant environment. `tenant-mongodb` is removed from the tenant baseline. The
baseline becomes `tenant-postgres`, `tenant-keycloak`, `tenant-minio` and `tenant-openbao`.

### 2. How non-relational data is stored
When a workload needs to store data that is not relational, it stays on PostgreSQL:
- **Documents and variable structures:** `JSONB` columns, with GIN indexes (`jsonb_path_ops` for containment queries,
  default `jsonb_ops` when key-existence operators are needed) and, when a field is queried often, an expression
  or generated column. JSON Schema rules can be enforced with `CHECK` constraints.
- **Other shapes:** PostgreSQL extensions, added to the tenant image only when a workload needs them and recorded in the
  ADR or spec of that workload: `pg_trgm` / full-text search for text, `hstore` for flat key-value maps, `ltree` for
  hierarchies, `PostGIS` for geodata, `pgvector` for embeddings, `pg_partman` / native partitioning for time series.
- **Files and large blobs** are not database data: they go to `tenant-minio`.
- One database per application, owned by a least-privilege role, provisioned by an idempotent script
  (`scripts/provision_caseforce_db.sh` is the pattern, ADR-0018).

### 3. Decommission `tenant-mongodb` in every namespace
For `swfabrik-europe` and `swfabrik-latam`: delete the StatefulSet, Service, PVC, PV and the `tenant-mongo-credentials`
Secret, and remove the manifests under `platform/kustomize/base/tnt-tenant-base/` and `platform/kustomize/overlays/tenants/*`,
the PVs in `storage-pvs.yaml`, the host directories in `scripts/setup_host_storage.sh`, the Makefile helper, the validation
check, the example under `apps/examples/tenant-xpto` and the Backstage catalog entries. The host directories are left in place
(they are empty, and removing them needs root).

## Consequences
- **Positive:** one engine to operate, back up and secure; two fewer StatefulSets, volumes and Secrets in the cluster; the
  heavy MongoDB probe disappears; the documented baseline matches what really runs.
- **Trade-off:** a workload that really needs a document store with its own scaling model must justify it in a new ADR.
  Until then JSONB is the answer.
- **Data:** nothing is lost: the volumes were empty.
- **Rollback:** the manifests stay in Git history (`platform/kustomize/base/tnt-tenant-base/tenant-mongodb.yaml`); bringing
  MongoDB back is a revert plus a new volume.
