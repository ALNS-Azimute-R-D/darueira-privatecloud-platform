# 15. GeoLocation Cleanup as a Temporal Workflow with a NiFi Flow for the Source Files

Date: 2026-09-26

## Status

Accepted

## Context

Importing a country (`GeoLocationIngestionWorkflow`) creates GeoLocations (level 0 = the country, level 1 =
its provinces), their assets (SVG maps, flag, detail PDF in the tenant MinIO), a copy of each detail report
in the corporate MinIO (`darueira-reports`), and the GADM source files (`raw/*.json`, `xml/*.xml`) in
`darueira-geodata`. There is no way to undo an import: until now the platform was cleaned by hand with SQL and
`mc`, which is error prone (which assets belong to which GeoLocation? which objects?).

## Decision

1. **Endpoint** `POST /api/v1/geolocations/workflows/cleanup` receives a collection of
   `{countrySlug, locationLevel, shouldDeleteJsonFile, shouldDeleteXmlFile}` plus `dryRun`. It starts a Temporal
   workflow and answers `202` with the workflow id, like `batch-import`; `GET .../cleanup/{id}/status` (query)
   and `.../result` follow it.
2. **`dryRun` defaults to `true`.** A dry run reads and reports the plan (what would be deleted, per item)
   and changes nothing; a real run needs `dryRun=false` explicitly.
3. **`GeoLocationCleanupWorkflow`**, on the same task queue as the import:
   1. `planCleanup(item)` for every item (read only): the GeoLocation ids, the assets, the tenant objects,
      the corporate report copies, the source files that exist, the provinces of a country, and any blockers.
   2. The request is **validated before anything is deleted**. A blocker anywhere stops the whole request
      with status `BLOCKED` (nothing is deleted), even with `dryRun=false`.
   3. With `dryRun=true` it returns the plan (`DRY_RUN`).
   4. Otherwise, items in descending level (provinces before their country), per item:
      `deleteAssetsAndGeoLocations` (backend), `deleteGeoDataFilesViaNiFi` (only when a file flag is set),
      `verifyCleanup`.
4. **Division of work.** The **backend** owns the database and the tenant/corporate objects: transactional,
   idempotent (a retry continues where it stopped) and it already owns the asset manager. **NiFi** owns
   the source files it created: a new process group "BookAnything - GeoLocation Cleanup Pipeline"
   (Kafka `geolocation.nifi-cleanup.requested` -> attributes -> optional `DeleteS3Object` of the JSON and of the
   XML -> summary -> Kafka `geolocation.nifi-cleanup.completed`), same request/reply pattern as the import.
   The flow definition is versioned in `platform/nifi/bookanything-geolocation-cleanup/` and applied by a script.
5. **Rules that the code enforces** (not left to the caller):
   - Only `COUNTRY` (level 0) and `PROVINCE` (level 1) are ever deleted. **`CONTINENT` and `REGION` are
     reference data (UN M49) and are never touched.** Levels other than 0 and 1 are rejected.
   - A **country with provinces** in the database is `BLOCKED` unless the same request also deletes its level 1
     (the plan of a country reports the number of provinces).
   - The detail reports (`darueira-reports/geolocations/geolocation-detail-report-*.pdf`) are deleted with
     their GeoLocation. **The job summaries (`job-geo-import-*-summary.pdf`) are never deleted**: they belong to
     an import, not to a country.
   - A GeoLocation referenced by addresses cannot be deleted: the step fails without retries and says so.
6. **No OIDC/OpenFGA on the endpoint for now** (decision of the owner, 2026-09-26): it is added once the
   whole flow runs 100%. Until then the endpoint is as open as the other workflow endpoints (backlog item 24),
   which is why the default is the read-only dry run.

## Consequences

- A cleanup is a workflow visible in the Temporal UI, with one step per item and retries.
- Reversing an import becomes a supported operation (and a way to test the import again from a clean base).
- The NiFi flow adds a second process group and a Kafka topic pair; the flow is code in the repository.
- The destructive part has no authorization yet: dry run by default is the only guard, so this must be
  closed before the endpoint is used outside the lab.
