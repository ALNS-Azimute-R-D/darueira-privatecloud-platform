#!/usr/bin/env python3
"""
generate_grafana_dashboards.py
Generates the Grafana dashboards of the Darueira Private Cloud that are built from code, into
platform/kustomize/base/corpshared-obs/dashboards/grafana/. Kustomize turns that folder into the ConfigMap
`grafana-dashboards-data`, which Grafana reads with file provisioning.

Only metrics that Prometheus really has are used. Prometheus scrapes cAdvisor (container_*, machine_*), kube-state-metrics
(kube_*), node-exporter (node_*), postgres-exporter (pg_*), Keycloak, APISIX and the OTel collector (ADR-0020).
Usage against limits comes from container_spec_*: the cluster defines no ResourceQuota objects.
Run scripts/validate_grafana_dashboards.py after changing a query: it evaluates every expression on Prometheus.

The two hand-maintained dashboards (apisix-metrics.json, k8s-pod-resource-analytics.json) live next to the generated ones.
"""

import json
import os

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "platform", "kustomize", "base",
                       "corpshared-obs", "dashboards", "grafana")
DS = {"type": "prometheus", "uid": "${DS}"}
CONTAINERS = 'container!="",container!="POD"'


# ----------------------------------------------------------------------------- panel helpers
def _target(expr, legend="", instant=False, table=False, ref="A"):
    t = {"refId": ref, "datasource": DS, "expr": expr, "legendFormat": legend, "instant": instant, "range": not instant}
    if table:
        t["format"] = "table"
    return t


def _steps(steps):
    return [{"color": c, "value": v} for c, v in steps]


def stat(title, expr, unit="short", steps=(("green", None),), legend="", decimals=None, description=""):
    defaults = {"unit": unit, "thresholds": {"mode": "absolute", "steps": _steps(steps)}, "color": {"mode": "thresholds"}}
    if decimals is not None:
        defaults["decimals"] = decimals
    return {"type": "stat", "title": title, "description": description, "datasource": DS,
            "fieldConfig": {"defaults": defaults, "overrides": []},
            "options": {"reduceOptions": {"calcs": ["lastNotNull"], "values": False}, "colorMode": "background",
                        "graphMode": "area", "textMode": "auto", "orientation": "auto"},
            "targets": [_target(expr, legend, instant=False)]}


def timeseries(title, targets, unit="short", stack=False, description="", minimum=None, maximum=None, legend_calcs=("lastNotNull", "max")):
    """targets: list of (expr, legend)."""
    custom = {"drawStyle": "line", "lineWidth": 1, "fillOpacity": 18, "showPoints": "never", "spanNulls": True,
              "stacking": {"mode": "normal" if stack else "none", "group": "A"}}
    defaults = {"unit": unit, "custom": custom}
    if minimum is not None:
        defaults["min"] = minimum
    if maximum is not None:
        defaults["max"] = maximum
    return {"type": "timeseries", "title": title, "description": description, "datasource": DS,
            "fieldConfig": {"defaults": defaults, "overrides": []},
            "options": {"legend": {"displayMode": "table", "placement": "bottom", "calcs": list(legend_calcs)},
                        "tooltip": {"mode": "multi", "sort": "desc"}},
            "targets": [_target(e, l, ref=chr(65 + i)) for i, (e, l) in enumerate(targets)]}


def bargauge(title, expr, unit="short", steps=(("green", None),), legend="{{pod}}", maximum=None, description=""):
    defaults = {"unit": unit, "thresholds": {"mode": "absolute", "steps": _steps(steps)}, "color": {"mode": "thresholds"}, "min": 0}
    if maximum is not None:
        defaults["max"] = maximum
    return {"type": "bargauge", "title": title, "description": description, "datasource": DS,
            "fieldConfig": {"defaults": defaults, "overrides": []},
            "options": {"reduceOptions": {"calcs": ["lastNotNull"], "values": False}, "orientation": "horizontal",
                        "displayMode": "gradient", "showUnconfigured": False, "valueMode": "color"},
            "targets": [_target(expr, legend, instant=True)]}


def table(title, expr, description="", value_name="Value"):
    return {"type": "table", "title": title, "description": description, "datasource": DS,
            "fieldConfig": {"defaults": {"custom": {"align": "auto"}}, "overrides": []},
            "options": {"showHeader": True, "sortBy": [{"displayName": value_name, "desc": True}]},
            "transformations": [{"id": "organize", "options": {"excludeByName": {"Time": True},
                                                               "renameByName": {"Value": value_name}}}],
            "targets": [_target(expr, instant=True, table=True)]}


def layout(rows):
    """rows: list of (height, [panels]). Panels of a row share the 24 columns equally."""
    panels, y, pid = [], 0, 1
    for height, row in rows:
        width = 24 // len(row)
        for i, p in enumerate(row):
            p["id"] = pid
            p["gridPos"] = {"h": height, "w": width, "x": i * width, "y": y}
            panels.append(p)
            pid += 1
        y += height
    return panels


def dashboard(uid, title, description, tags, rows, variables=(), refresh="30s", time_from="now-6h"):
    ds_var = {"name": "DS", "label": "Prometheus", "type": "datasource", "query": "prometheus", "current": {}, "hide": 0,
              "includeAll": False, "multi": False, "options": [], "refresh": 1, "regex": "", "skipUrlSync": False}
    return {"uid": uid, "title": title, "description": description, "tags": ["darueira"] + list(tags),
            "schemaVersion": 39, "version": 1, "editable": True, "graphTooltip": 1, "refresh": refresh,
            "time": {"from": time_from, "to": "now"}, "timezone": "browser", "annotations": {"list": []},
            "templating": {"list": [ds_var] + list(variables)}, "links": [], "panels": layout(rows)}


def query_variable(name, label, query, default_all=True, regex=""):
    return {"name": name, "label": label, "type": "query", "datasource": DS, "query": {"query": query, "refId": f"{name}-var"},
            "definition": query, "refresh": 2, "sort": 1, "multi": True, "includeAll": True, "allValue": ".*",
            "current": {"selected": True, "text": "All", "value": "$__all"} if default_all else {}, "regex": regex,
            "hide": 0, "options": [], "skipUrlSync": False}


# ----------------------------------------------------------------------------- dashboards
def platform_overview():
    # The uid must stay the one the file platform-overview.json always had: Grafana ties a provisioned file to its dashboard,
    # and a different uid for the same file fails with "could not resolve dashboards:uid:<uid>: Dashboard not found".
    cpu = f'sum(rate(container_cpu_usage_seconds_total{{{CONTAINERS}}}[5m]))'
    return dashboard(
        "darueira-platform-overview", "Darueira Platform - Control Plane Overview",
        "Health of the single-node cluster: node load, memory pressure, OOM kills, gateway traffic and scrape targets. "
        "Node figures come from the cAdvisor root cgroup (there is no node-exporter).",
        ["overview", "platform"], [
            (4, [
                stat("Running containers", f'count(count by (namespace,pod,container) (container_memory_working_set_bytes{{{CONTAINERS}}}))'),
                stat("Node CPU", '100 * sum(rate(container_cpu_usage_seconds_total{id="/"}[5m])) / max(machine_cpu_cores)', "percent",
                     (("green", None), ("yellow", 60), ("red", 80)), decimals=1),
                stat("Node memory", '100 * sum(container_memory_working_set_bytes{id="/"}) / max(machine_memory_bytes)', "percent",
                     (("green", None), ("yellow", 75), ("red", 90)), decimals=1),
                stat("OOM kills (24h)", 'sum(increase(container_oom_events_total{container!=""}[24h])) or vector(0)', "short",
                     (("green", None), ("red", 1)), description="Containers killed for exceeding their memory limit."),
                stat("Gateway requests/s", 'sum(rate(apisix_http_status[5m])) or vector(0)', "reqps", decimals=2),
                stat("Gateway 5xx", '100 * sum(rate(apisix_http_status{code=~"5.."}[5m])) / sum(rate(apisix_http_status[5m])) or vector(0)',
                     "percent", (("green", None), ("yellow", 1), ("red", 5)), decimals=2),
                stat("Scrape targets down", 'count(up == 0) or vector(0)', "short", (("green", None), ("red", 1)),
                     description="Prometheus targets that fail to scrape. See the Observability Stack dashboard."),
            ]),
            (8, [
                timeseries("CPU by namespace (top 8)", [(f'topk(8, sum by (namespace) (rate(container_cpu_usage_seconds_total{{{CONTAINERS}}}[5m])))', "{{namespace}}")], "none"),
                timeseries("Memory by namespace (top 8)", [(f'topk(8, sum by (namespace) (container_memory_working_set_bytes{{{CONTAINERS}}}))', "{{namespace}}")], "bytes"),
            ]),
            (8, [
                timeseries("Gateway status codes", [('sum by (code) (rate(apisix_http_status[5m]))', "{{code}}")], "reqps", stack=True),
                timeseries("Pod network (all pods)", [('sum(rate(container_network_receive_bytes_total{pod!=""}[5m]))', "receive"),
                                                       ('sum(rate(container_network_transmit_bytes_total{pod!=""}[5m]))', "transmit")], "Bps"),
            ]),
            (9, [
                bargauge("Memory by namespace", f'sort_desc(sum by (namespace) (container_memory_working_set_bytes{{{CONTAINERS}}}))', "bytes",
                         legend="{{namespace}}"),
                bargauge("CPU by namespace (cores)", f'sort_desc({cpu.replace("sum(", "sum by (namespace) (", 1)})', "none", legend="{{namespace}}"),
            ]),
        ])


def tenant_resources():
    ns = 'namespace=~"$ns"'
    sel = f'{ns},{CONTAINERS}'
    mem_ratio = (f'100 * max by (namespace,pod) (container_memory_working_set_bytes{{{sel}}}) / '
                 f'max by (namespace,pod) (container_spec_memory_limit_bytes{{{sel}}} > 0)')
    cpu_ratio = (f'100 * sum by (namespace,pod) (rate(container_cpu_usage_seconds_total{{{sel}}}[5m])) / '
                 f'(max by (namespace,pod) (container_spec_cpu_quota{{{sel}}} > 0) / max by (namespace,pod) (container_spec_cpu_period{{{sel}}}))')
    return dashboard(
        "tenant-resources", "Darueira Tenants - Resource Usage vs Limits",
        "CPU and memory of the selected tenant namespaces against the limits of their containers. Replaces the old quota "
        "dashboard, which needed kube-state-metrics (not installed).",
        ["tenants", "resources", "capacity"], [
            (4, [
                stat("Memory (working set)", f'sum(container_memory_working_set_bytes{{{sel}}})', "bytes"),
                stat("CPU (cores)", f'sum(rate(container_cpu_usage_seconds_total{{{sel}}}[5m]))', "none", decimals=2),
                stat("Running containers", f'count(count by (namespace,pod,container) (container_memory_working_set_bytes{{{sel}}}))'),
                stat("Pods above 90% of memory limit", f'count(({mem_ratio}) > 90) or vector(0)', "short", (("green", None), ("red", 1))),
            ]),
            (10, [
                bargauge("Memory used / limit (%)", mem_ratio, "percent", (("green", None), ("yellow", 70), ("red", 90)), maximum=100),
                bargauge("CPU used / limit (%)", cpu_ratio, "percent", (("green", None), ("yellow", 70), ("red", 90)), maximum=100),
            ]),
            (8, [
                timeseries("Memory by pod", [(f'sum by (pod) (container_memory_working_set_bytes{{{sel}}})', "{{pod}}")], "bytes"),
                timeseries("CPU by pod (cores)", [(f'sum by (pod) (rate(container_cpu_usage_seconds_total{{{sel}}}[5m]))', "{{pod}}")], "none"),
            ]),
            (8, [
                timeseries("CPU throttling (% of periods)",
                           [(f'100 * sum by (pod) (rate(container_cpu_cfs_throttled_periods_total{{{sel}}}[5m])) / sum by (pod) (rate(container_cpu_cfs_periods_total{{{sel}}}[5m]))', "{{pod}}")],
                           "percent", description="A pod that is throttled is running slower than it could: raise its CPU limit.", minimum=0),
                timeseries("Network (receive + transmit)", [(f'sum by (pod) (rate(container_network_receive_bytes_total{{{ns},pod!=""}}[5m]) + rate(container_network_transmit_bytes_total{{{ns},pod!=""}}[5m]))', "{{pod}}")], "Bps"),
            ]),
        ],
        variables=[query_variable("ns", "Tenant namespace", 'label_values(container_memory_working_set_bytes{namespace=~"drr-tnt-.*"}, namespace)')])


def containers_health():
    ns = 'namespace=~"$ns"'
    sel = f'{ns},{CONTAINERS}'
    restarted = f'changes(container_start_time_seconds{{{sel}}}[1h]) > 0'
    mem_ratio = (f'100 * max by (namespace,pod) (container_memory_working_set_bytes{{{sel}}}) / '
                 f'max by (namespace,pod) (container_spec_memory_limit_bytes{{{sel}}} > 0)')
    throttle = (f'100 * sum by (namespace,pod) (rate(container_cpu_cfs_throttled_periods_total{{{sel}}}[5m])) / '
                f'sum by (namespace,pod) (rate(container_cpu_cfs_periods_total{{{sel}}}[5m]))')
    return dashboard(
        "containers-health", "Darueira Platform - Containers Health",
        "Where containers hurt: OOM kills, restarts, memory close to the limit, CPU throttling and network errors. "
        "Restarts are detected through container_start_time_seconds (there is no kube-state-metrics).",
        ["health", "kubernetes", "oom", "restarts"], [
            (4, [
                stat("OOM kills (24h)", f'sum(increase(container_oom_events_total{{{sel}}}[24h])) or vector(0)', "short", (("green", None), ("red", 1))),
                stat("Containers restarted (1h)", f'count({restarted}) or vector(0)', "short", (("green", None), ("yellow", 1), ("red", 5))),
                stat("Above 90% of memory limit", f'count(({mem_ratio}) > 90) or vector(0)', "short", (("green", None), ("red", 1))),
                stat("Throttled above 25%", f'count(({throttle}) > 25) or vector(0)', "short", (("green", None), ("yellow", 1), ("red", 5))),
            ]),
            (8, [
                table("OOM-killed containers (24h)", f'topk(20, increase(container_oom_events_total{{{sel}}}[24h]) > 0)', value_name="OOM kills"),
                table("Restarted containers (1h)", f'topk(20, {restarted})', value_name="Restarts"),
            ]),
            (9, [
                timeseries("Memory used / limit (top 10, %)", [(f'topk(10, {mem_ratio})', "{{pod}}")], "percent", minimum=0, maximum=100),
                timeseries("CPU throttling (top 10, %)", [(f'topk(10, {throttle})', "{{pod}}")], "percent", minimum=0),
            ]),
            (8, [
                timeseries("Network errors by namespace", [(f'sum by (namespace) (rate(container_network_receive_errors_total{{{ns},pod!=""}}[5m]) + rate(container_network_transmit_errors_total{{{ns},pod!=""}}[5m]))', "{{namespace}}")], "pps"),
                timeseries("Dropped packets by namespace", [(f'sum by (namespace) (rate(container_network_receive_packets_dropped_total{{{ns},pod!=""}}[5m]) + rate(container_network_transmit_packets_dropped_total{{{ns},pod!=""}}[5m]))', "{{namespace}}")], "pps"),
            ]),
        ],
        variables=[query_variable("ns", "Namespace", 'label_values(container_memory_working_set_bytes, namespace)')])


def keycloak_jvm():
    j = 'job="keycloak"'
    return dashboard(
        "keycloak-jvm", "Keycloak - JVM, HTTP & Database Pool",
        "The central identity provider (job keycloak): JVM memory, garbage collection, threads, the database connection pool "
        "(Agroal) and the HTTP server.",
        ["keycloak", "iam", "jvm"], [
            (4, [
                stat("Up", f'max(up{{{j}}})', "short", (("red", None), ("green", 1))),
                stat("JVM heap used", f'100 * sum(jvm_memory_used_bytes{{{j},area="heap"}}) / sum(jvm_memory_max_bytes{{{j},area="heap"}})', "percent",
                     (("green", None), ("yellow", 70), ("red", 90)), decimals=1),
                stat("Live threads", f'max(jvm_threads_live_threads{{{j}}})'),
                stat("DB connections active", f'sum(agroal_active_count{{{j}}})', "short", (("green", None), ("yellow", 8))),
                stat("DB requests waiting", f'sum(agroal_awaiting_count{{{j}}})', "short", (("green", None), ("red", 1))),
                stat("Process CPU", f'100 * max(process_cpu_usage{{{j}}})', "percent", decimals=1),
            ]),
            (8, [
                timeseries("JVM memory by pool", [(f'sum by (area,id) (jvm_memory_used_bytes{{{j}}})', "{{area}} {{id}}")], "bytes", stack=True),
                timeseries("Garbage collection (pause time/s)", [(f'sum by (action) (rate(jvm_gc_pause_seconds_sum{{{j}}}[5m]))', "{{action}}")], "s"),
            ]),
            (8, [
                timeseries("Database pool (Agroal)", [(f'sum(agroal_active_count{{{j}}})', "active"), (f'sum(agroal_available_count{{{j}}})', "available"),
                                                       (f'sum(agroal_awaiting_count{{{j}}})', "awaiting")], "short"),
                timeseries("Database connections acquired/s", [(f'sum(rate(agroal_acquire_count_total{{{j}}}[5m]))', "acquired")], "ops"),
            ]),
            (8, [
                timeseries("HTTP active requests", [(f'sum(http_server_active_requests{{{j}}})', "active")], "short"),
                timeseries("HTTP bytes written/s", [(f'sum(rate(http_server_bytes_written_sum{{{j}}}[5m]))', "written")], "Bps"),
            ]),
            (8, [
                timeseries("Live threads", [(f'max(jvm_threads_live_threads{{{j}}})', "live"), (f'max(jvm_threads_daemon_threads{{{j}}})', "daemon")], "short"),
                timeseries("Session expiration task (avg duration)",
                           [(f'rate(keycloak_session_expiration_task_seconds_sum{{{j}}}[5m]) / rate(keycloak_session_expiration_task_seconds_count{{{j}}}[5m])', "avg")], "s"),
            ]),
        ])


def observability_stack():
    obs = f'namespace="drr-corpshared-obs",{CONTAINERS}'
    return dashboard(
        "observability-stack", "Darueira Observability - Stack Cost & Scrape Targets",
        "What the observability stack itself costs (OpenSearch is a JVM) and which Prometheus targets are healthy.",
        ["observability", "prometheus", "opensearch"], [
            (4, [
                stat("Targets up", 'count(up == 1) or vector(0)', "short", (("red", None), ("green", 1))),
                stat("Targets down", 'count(up == 0) or vector(0)', "short", (("green", None), ("red", 1))),
                stat("Stack memory", f'sum(container_memory_working_set_bytes{{{obs}}})', "bytes"),
                stat("Share of node memory", f'100 * sum(container_memory_working_set_bytes{{{obs}}}) / max(machine_memory_bytes)', "percent", decimals=1),
                stat("Stack CPU (cores)", f'sum(rate(container_cpu_usage_seconds_total{{{obs}}}[5m]))', "none", decimals=2),
            ]),
            (8, [
                table("Scrape targets (1 = up)", 'sort(up)', value_name="Up"),
                bargauge("Memory by pod", f'sort_desc(sum by (pod) (container_memory_working_set_bytes{{{obs}}}))', "bytes"),
            ]),
            (8, [
                timeseries("Memory by pod", [(f'sum by (pod) (container_memory_working_set_bytes{{{obs}}})', "{{pod}}")], "bytes"),
                timeseries("CPU by pod (cores)", [(f'sum by (pod) (rate(container_cpu_usage_seconds_total{{{obs}}}[5m]))', "{{pod}}")], "none"),
            ]),
        ])


def kubernetes_state():
    ns = 'namespace=~"$ns"'
    return dashboard(
        "kubernetes-state", "Darueira Kubernetes - Workload State",
        "Replicas, pod phases, restarts and volumes, from kube-state-metrics.",
        ["kubernetes", "workloads"], [
            (4, [
                stat("Pods running", f'sum(kube_pod_status_phase{{{ns},phase="Running"}})'),
                stat("Pods not ready/failed", f'sum(kube_pod_status_phase{{{ns},phase=~"Failed|Unknown|Pending"}}) or vector(0)', "short", (("green", None), ("red", 1))),
                stat("Deployments below desired", f'count(kube_deployment_spec_replicas{{{ns}}} > kube_deployment_status_replicas_available{{{ns}}}) or vector(0)', "short", (("green", None), ("red", 1)),
                     description="Includes deployments scaled to 0 on purpose only when desired replicas > 0."),
                stat("StatefulSets below desired", f'count(kube_statefulset_replicas{{{ns}}} > kube_statefulset_status_replicas_ready{{{ns}}}) or vector(0)', "short", (("green", None), ("red", 1))),
                stat("Restarts (1h)", f'sum(increase(kube_pod_container_status_restarts_total{{{ns}}}[1h])) or vector(0)', "short", (("green", None), ("yellow", 3), ("red", 10))),
                stat("PVCs not bound", f'sum(kube_persistentvolumeclaim_status_phase{{{ns},phase!="Bound"}}) or vector(0)', "short", (("green", None), ("red", 1))),
            ]),
            (9, [
                table("Deployments below desired replicas",
                      f'kube_deployment_spec_replicas{{{ns}}} - kube_deployment_status_replicas_available{{{ns}}} > 0',
                      description="Empty means every deployment has all its replicas."),
                table("Pods not running", f'kube_pod_status_phase{{{ns},phase=~"Failed|Unknown|Pending"}} == 1'),
            ]),
            (8, [
                timeseries("Pods by phase", [(f'sum by (phase) (kube_pod_status_phase{{{ns}}})', "{{phase}}")], "short", stack=True),
                timeseries("Container restarts (top 10 pods, 1h)", [(f'topk(10, sum by (namespace,pod) (increase(kube_pod_container_status_restarts_total{{{ns}}}[1h])))', "{{namespace}}/{{pod}}")], "short"),
            ]),
            (8, [
                bargauge("Pods by namespace", 'sort_desc(count by (namespace) (kube_pod_info{namespace=~"$ns"}))', "short", legend="{{namespace}}"),
                bargauge("Requested memory by namespace", f'sort_desc(sum by (namespace) (kube_pod_container_resource_requests{{{ns},resource="memory"}}))', "bytes", legend="{{namespace}}"),
            ]),
        ],
        variables=[query_variable("ns", "Namespace", 'label_values(kube_pod_info, namespace)')])


def host_node():
    fs = 'fstype!~"tmpfs|overlay|squashfs|ramfs",mountpoint!~"/host/root/(snap|boot).*"'
    return dashboard(
        "host-node", "Darueira Host - Node Health",
        "CPU, memory, load, disk and filesystems of the host that runs the whole cluster, from node-exporter. "
        "The shared HDD is the known bottleneck (docs/runbooks/host-disk-io-contention.md).",
        ["host", "node", "capacity"], [
            (4, [
                stat("CPU busy", '100 * (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])))', "percent", (("green", None), ("yellow", 60), ("red", 85)), decimals=1),
                stat("Memory used", '100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)', "percent", (("green", None), ("yellow", 75), ("red", 90)), decimals=1),
                stat("Load 1m / cores", 'node_load1 / scalar(count(count by (cpu) (node_cpu_seconds_total{mode="idle"})))', "none", (("green", None), ("yellow", 0.7), ("red", 1)), decimals=2),
                stat("Disk busy (max device)", '100 * max(rate(node_disk_io_time_seconds_total[5m]))', "percent", (("green", None), ("yellow", 60), ("red", 90)), decimals=0,
                     description="Time the busiest device had IO in flight. Near 100% = the shared HDD is saturated."),
                stat("Swap used", '100 * (1 - node_memory_SwapFree_bytes / node_memory_SwapTotal_bytes) or vector(0)', "percent", (("green", None), ("yellow", 10), ("red", 50)), decimals=0),
                stat("Uptime", 'time() - node_boot_time_seconds', "s"),
            ]),
            (8, [
                timeseries("CPU by mode", [('sum by (mode) (rate(node_cpu_seconds_total{mode!="idle"}[5m])) / scalar(count(count by (cpu) (node_cpu_seconds_total{mode="idle"})))', "{{mode}}")], "percentunit", stack=True),
                timeseries("Memory", [('node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes', "used"), ('node_memory_Cached_bytes', "page cache"), ('node_memory_MemAvailable_bytes', "available")], "bytes"),
            ]),
            (8, [
                timeseries("Disk throughput", [('sum by (device) (rate(node_disk_read_bytes_total[5m]))', "read {{device}}"), ('sum by (device) (rate(node_disk_written_bytes_total[5m]))', "write {{device}}")], "Bps"),
                timeseries("Disk busy and IO wait", [('100 * rate(node_disk_io_time_seconds_total[5m])', "busy {{device}}"), ('100 * avg(rate(node_cpu_seconds_total{mode="iowait"}[5m]))', "CPU iowait")], "percent", minimum=0),
            ]),
            (8, [
                bargauge("Filesystem used (%)", f'100 * (1 - node_filesystem_avail_bytes{{{fs}}} / node_filesystem_size_bytes{{{fs}}})', "percent", (("green", None), ("yellow", 75), ("red", 90)), legend="{{mountpoint}}", maximum=100),
                timeseries("Load average", [('node_load1', "1m"), ('node_load5', "5m"), ('node_load15', "15m")], "none"),
            ]),
        ])


def postgresql():
    pg = 'instance_name=~"$pg"'
    return dashboard(
        "postgresql", "Darueira Data - PostgreSQL",
        "central-postgres and the tenant-postgres of every tenant, from postgres-exporter (role drr_monitor, pg_monitor).",
        ["postgresql", "data"], [
            (4, [
                stat("Instances up", f'sum(pg_up{{{pg}}})'),
                stat("Connections", f'sum(pg_stat_activity_count{{{pg}}})'),
                stat("Commits/s", f'sum(rate(pg_stat_database_xact_commit{{{pg}}}[5m]))', "ops", decimals=1),
                stat("Rollbacks/s", f'sum(rate(pg_stat_database_xact_rollback{{{pg}}}[5m]))', "ops", (("green", None), ("yellow", 1)), decimals=2),
                stat("Cache hit ratio", f'100 * sum(rate(pg_stat_database_blks_hit{{{pg}}}[5m])) / (sum(rate(pg_stat_database_blks_hit{{{pg}}}[5m])) + sum(rate(pg_stat_database_blks_read{{{pg}}}[5m])))',
                     "percent", (("red", None), ("yellow", 90), ("green", 97)), decimals=1),
                stat("Deadlocks (1h)", f'sum(increase(pg_stat_database_deadlocks{{{pg}}}[1h])) or vector(0)', "short", (("green", None), ("red", 1))),
            ]),
            (8, [
                timeseries("Connections by instance", [(f'sum by (instance_name) (pg_stat_activity_count{{{pg}}})', "{{instance_name}}")], "short"),
                timeseries("Transactions/s", [(f'sum by (instance_name) (rate(pg_stat_database_xact_commit{{{pg}}}[5m]))', "commit {{instance_name}}"),
                                              (f'sum by (instance_name) (rate(pg_stat_database_xact_rollback{{{pg}}}[5m]))', "rollback {{instance_name}}")], "ops"),
            ]),
            (8, [
                bargauge("Database size", f'sort_desc(pg_database_size_bytes{{{pg},datname!~"template.*"}})', "bytes", legend="{{instance_name}} / {{datname}}"),
                timeseries("Rows returned/fetched per second", [(f'sum by (instance_name) (rate(pg_stat_database_tup_returned{{{pg}}}[5m]))', "returned {{instance_name}}"),
                                                                (f'sum by (instance_name) (rate(pg_stat_database_tup_fetched{{{pg}}}[5m]))', "fetched {{instance_name}}")], "ops"),
            ]),
            (8, [
                timeseries("Temp files bytes/s", [(f'sum by (instance_name) (rate(pg_stat_database_temp_bytes{{{pg}}}[5m]))', "{{instance_name}}")], "Bps",
                           description="Queries spilling to disk: sort/hash that does not fit in work_mem."),
                timeseries("Longest transaction (s)", [(f'max by (instance_name) (pg_stat_activity_max_tx_duration{{{pg}}})', "{{instance_name}}")], "s"),
            ]),
        ],
        variables=[query_variable("pg", "Instance", 'label_values(pg_up, instance_name)')])


GENERATED = {
    "platform-overview.json": platform_overview,
    "tenant-resources.json": tenant_resources,
    "containers-health.json": containers_health,
    "keycloak-jvm.json": keycloak_jvm,
    "observability-stack.json": observability_stack,
    "kubernetes-state.json": kubernetes_state,
    "host-node.json": host_node,
    "postgresql.json": postgresql,
}

if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, fn in GENERATED.items():
        with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as f:
            json.dump(fn(), f, indent=2, ensure_ascii=False)
            f.write("\n")
    print(f"Generated {len(GENERATED)} Grafana dashboards into {os.path.normpath(OUT_DIR)}")
