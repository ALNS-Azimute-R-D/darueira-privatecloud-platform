# ADR 0020: Observability Stack Upgrade, Metric Exporters and 3-Day Log Retention

## Status
Accepted (2026-11-22). Amends the observability tier of `specs/01-initial-spec.md` (`drr-corpshared-obs`).

## Context
The stack in `drr-corpshared-obs` was pinned to mid-2024 versions (Grafana 11.1.0, Prometheus 2.53.1, OpenSearch and
Dashboards 2.15.0, Jaeger 1.59 all-in-one, OTel Collector 0.106.1, Fluent Bit 3.1.4). After the 2026-11-08 host disk failure a
review (backlog item 44) found:
- Grafana dashboards depended on `node-exporter` and `kube-state-metrics`, which are not installed; there are no
  database metrics at all;
- the Grafana "OpenSearch" datasource is dead (plugin absent);
- the Prometheus target `drr-iam-authz-svc` has been down since it was added: the service exposes no `/metrics`;
- the ISM retention policy was in Git but not installed, so 14 daily log indices (~3 GB) piled up on a shared HDD.

## Decision

### 1. Upgrade to the latest stable releases (checked against the official GitHub releases and Docker Hub on 2026-11-22)
| Component | From | To | Notes |
|---|---|---|---|
| Prometheus | v2.53.1 | v3.16.0 | v3 reads v2 TSDB; rollback is only possible to 2.55 |
| Grafana | 11.1.0 | 13.3.1 | state is `emptyDir` and fully provisioned from files, so no DB migration risk |
| OpenSearch | 2.15.0 | 2.19.7 then 3.10.0 | 3.x supports upgrades only from 2.19; two hops, one restart each |
| OpenSearch Dashboards | 2.15.0 | 3.10.0 | must match OpenSearch |
| Jaeger | 1.59.0 all-in-one | 2.23.0 | v1 reached end of life; v2 is configured by an OTel-style YAML |
| OTel Collector (contrib) | 0.106.1 | 0.165.0 | `0.165.1` is not on Docker Hub yet |
| Fluent Bit | 3.1.4 | 5.2.0 | |
Each step is applied alone, validated, and committed; a failed step is reverted without touching the next ones.

### 2. Grafana datasource and plugin
The `grafana-opensearch-datasource` plugin is installed at start (`GF_PLUGINS_PREINSTALL`), the datasource points to the real
index pattern (`darueira-k8s-logs-*`, time field `@timestamp`) and the OpenSearch version of the cluster. Grafana credentials
move from literal values in the Deployment to a Secret (guardrail: no hardcoded credentials).

### 3. New exporters (PaaS, `drr-corpshared-obs`)
- `kube-state-metrics` (replicas, quotas, pod phases), `node-exporter` (host CPU, memory, disk I/O, filesystem),
- `postgres_exporter` for each `tenant-postgres` and for the system PostgreSQL, using a dedicated role in the `pg_monitor`
  group; passwords only in Secrets, never in Git.
Every new workload has resource requests/limits and a Cilium NetworkPolicy.

### 4. Targets
`drr-iam-authz-svc` is removed from the scrape list until the service implements `/metrics` (tracked in the backlog); a target
that can never be up only hides real failures. Probe-level availability of that service stays covered by the APISIX metrics.

### 5. Log retention: 3 days
The ISM policy `darueira-k8s-logs-retention` deletes `darueira-k8s-logs-*` indices older than 3 days (was 2 in Git, 0 installed).
`scripts/bootstrap_observability.py` is the installer and is idempotent.

## Consequences
- **Positive:** supported versions with security fixes; dashboards for replicas, quotas, host and database health; bounded log disk use.
- **Cost:** a few hundred MB of RAM for the exporters on a host with ~17 GB available; one restart per upgraded component.
- **Risk:** major jumps (Prometheus 3, OpenSearch 3, Jaeger 2, Fluent Bit 5) can change flags and config. Mitigation: staged rollout,
  config validated before applying (`promtool`, collector `validate`), previous manifests in Git history.
- **Data:** old log indices are deleted by retention on purpose; metrics history (Prometheus PVC) is kept.
