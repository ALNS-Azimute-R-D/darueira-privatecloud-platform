# 14. GeoLocation Artifact Generation as Per-Item Temporal Workflows

Date: 2026-09-26

## Status

Accepted

## Context

The BookAnything GeoLocation import (`GeoLocationIngestionWorkflow`, Temporal) ends when the NiFi ingestion
and the job summary PDF are done. The per-GeoLocation artifacts (SVG maps, flag, AI summary, detail PDF)
are generated **outside Temporal**: `GeoLocationEnrichmentKafkaConsumer` (group `geolocation-enricher`)
calls the `generateGeoLocationArtifactsAndReport` method as a plain Kotlin call whenever a GeoLocation is
created or updated. Consequences seen in the DEU/BRA/USA imports (2026-09-26):

1. **No visibility**: the Temporal UI shows the workflow as finished while ~70 items are still being
   generated for minutes; there is no start/end/duration/retry per item.
2. **No retry granularity**: the method catches every exception and returns a DTO with `status=ERROR`, so
   Temporal never retries; the JSReport `Target closed` failures are retried by a private loop that
   re-runs nothing else, and one late failure loses the SVGs/AI work already done.
3. **Unbounded CPU pressure**: NiFi POSTs (province creation) compete for the 1.5 CPU limit of the Pod
   with the GeoPandas subprocess of the artifacts; the USA level 1 run showed 15 `SocketTimeoutException`s
   in NiFi (the backend still persisted the records).
4. **Temporal payload limit**: activity inputs and outputs go through the workflow history (2 MB per
   payload, warning from 256 KB). The steps of the current method exchange SVGs (47-308 KB and more for
   large states), the flag and the PDF (up to ~700 KB) in memory, so they cannot simply become activities
   that pass those bytes.

## Decision

1. **`GeoLocationArtifactsWorkflow`, one execution per GeoLocation.** Workflow id `geo-artifacts-<id>`
   (deterministic), dedicated task queue `GEOLOCATION_ARTIFACTS_TASK_QUEUE`. The memo carries the
   GeoLocation id, name and type. Its steps are separate activities so each one has its own start, end,
   duration and retry policy: `generateAndStoreMaps`, `resolveAndStoreFlag`, `enrichWithAi`,
   `renderAndStoreReport`, `copyReportToCorporateStorage`.
2. **Steps exchange references, never content.** Each activity persists its output (assets in the tenant
   MinIO, the AI summary in the entity details) and returns only ids, URLs and short strings. The report
   step re-reads the SVGs and the flag from their assets through the storage port. Activities **throw**
   on failure (so Temporal retries); only terminal business outcomes (`SKIPPED_NO_GEOMETRY`) are returned.
3. **Concurrency window of 4 in the worker**, not in the caller: the artifacts worker is created with
   `maxConcurrentActivityExecutionSize = 4` (`temporal.artifacts.max-concurrent-activities`). Workflows can
   be started freely; the extra activities wait scheduled in the queue, which is visible in the UI.
   The limit is per worker (per Pod): with more replicas the effective window multiplies.
4. **Trigger stays event-driven.** `GeoLocationEnrichmentKafkaConsumer` keeps the AI boundary logic and
   **starts** the workflow (asynchronously, without waiting) instead of calling the method. Starting an id
   that is already running is treated as "already there" (`WorkflowExecutionAlreadyStarted`); the reuse
   policy allows a new run after a previous one closed (a re-import regenerates the artifacts). This also
   covers GeoLocations created through the plain REST API.
5. **The import workflow waits for them.** After the NiFi loop, a new stage `ARTIFACTS` runs the activity
   `awaitArtifactWorkflows(countrySlug, locationLevel)`: it lists the GeoLocation ids from the **database**
   (not from the NiFi counters, which were wrong for the USA), starts any missing workflow, and waits for
   each result with heartbeats. The batch result reports how many succeeded, were skipped or failed.
6. **REST endpoint `POST .../{geoLocationId}/artifacts-and-report`** starts the same workflow and waits for
   its result, so the manual path is also visible in Temporal and there is a single implementation.
7. The former monolithic activity `generateGeoLocationArtifactsAndReport` is removed from
   `GeoLocationIngestionActivities`.

### Alternatives considered

- **Real child workflows started by the import workflow (window in the parent), with a flag sent by NiFi
  step 8 so the Kafka consumer skips those items.** Rejected: it changes the versioned NiFi script and the
  enrichment event, and GeoLocations created through the API would need another trigger.
- **Passing SVGs/flag/PDF bytes between activities.** Rejected because of the 2 MB payload limit and the
  history size.
- **Custom search attributes (`GeoLocationId`, `CountrySlug`).** Deferred: registering them is a change to
  the Temporal namespace (cluster mutation). The workflow id prefix `geo-artifacts-` and the memo are
  used meanwhile.

## Consequences

- Each GeoLocation is a workflow in the Temporal UI (filter by id prefix `geo-artifacts-`), with per-step
  timings; a JSReport failure retries only the report step.
- The import workflow only completes when the artifacts are done, and its result no longer depends on the
  NiFi counters for that.
- CPU pressure from artifact generation is bounded to 4 concurrent activities per Pod.
- The artifact workflows are not Temporal *children* of the import workflow (they are independent
  executions, linked by id convention).
- New `@WorkflowInterface`/`@ActivityInterface` types are registered for the native image automatically by
  `NativeRuntimeHints` (it scans the application package), but the native build must be tested locally.
- Follow-ups: custom search attributes; the cleanup workflow (backlog item 28) reuses this pattern.
