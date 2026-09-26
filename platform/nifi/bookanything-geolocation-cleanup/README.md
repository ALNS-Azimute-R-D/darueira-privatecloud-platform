# NiFi: BookAnything - GeoLocation Cleanup Pipeline

Deletes the **source files** (`raw/gadm41_<ISO3>_<level>.json` and `xml/gadm41_<ISO3>_<level>.xml` in the
`darueira-geodata` bucket) of an imported country/level. Part of the GeoLocation cleanup (ADR-0015): the
Temporal workflow `GeoLocationCleanupWorkflow` deletes the database rows and the assets itself and only asks
this flow for the files, through Kafka. The import pipeline (`bookanything-geolocation-ingestion`) is a
separate group and is never touched by anything here.

```
1. Consume Cleanup Request      Kafka geolocation.nifi-cleanup.requested
2. Extract Cleanup Attributes   jobId, countrySlug, locationLevel, shouldDeleteJsonFile, shouldDeleteXmlFile
3. Route on shouldDeleteJsonFile --delete_json--> 4. Delete Raw GeoJSON --failure--> 4b. Mark JSON Delete Failure
5. Route on shouldDeleteXmlFile  --delete_xml---> 6. Delete XML         --failure--> 6b. Mark XML Delete Failure
7. Summarize Cleanup            Groovy: 07-summarize-cleanup.groovy (always answers, with errorMessage on failure)
8. Publish Cleanup Event        Kafka geolocation.nifi-cleanup.completed
```

Request: `{"jobId","countrySlug","locationLevel","shouldDeleteJsonFile","shouldDeleteXmlFile"}`.
Reply: `{"jobId","countrySlug","locationLevel","deletedJson","deletedXml","failedCount","durationMs"[,"errorMessage"]}`.
Deleting a key that does not exist is not an error (S3 semantics), so the reply reports what was *requested* and
succeeded, not whether the file existed: the dry run of the backend reports which files exist.

## The flow is code

`flow.json` is the source of truth. Do not edit the group in the NiFi UI.

```bash
make check-nifi-cleanup-flow    # diff flow.json against the live flow (read only)
make apply-nifi-cleanup-flow    # create/update it (mutating: one agent at a time)
make test-nifi-cleanup-script   # step 7 offline (needs groovy)
```

`{{CENTRAL_MINIO_ACCESS_KEY}}` / `{{CENTRAL_MINIO_SECRET_KEY}}` in `flow.json` are resolved from the environment
of the central-minio pod when the flow is applied; no secret is stored in the repository (the S3 processors
still hold static credentials, like the import flow: backlog item 25).

## Smoke test without the backend

```bash
echo '{"jobId":"t1","countrySlug":"ZZZ","locationLevel":1,"shouldDeleteJsonFile":true,"shouldDeleteXmlFile":true}' \
  | kubectl -n drr-corpshared-plat exec -i deploy/message-broker-kafka -c redpanda -- rpk topic produce geolocation.nifi-cleanup.requested
kubectl -n drr-corpshared-plat exec deploy/message-broker-kafka -c redpanda -- \
  rpk topic consume geolocation.nifi-cleanup.completed -o -1 -n 1
```
