#!/usr/bin/env python3
"""
generate_grafana_dashboards.py
Generates the Grafana dashboards of the Darueira Private Cloud that are built from code, into
platform/kustomize/base/corpshared-obs/dashboards/grafana/. Kustomize turns that folder into the ConfigMap
`grafana-dashboards-data`, which Grafana reads with file provisioning.

Only metrics that Prometheus really has are used. Prometheus scrapes cAdvisor (container_*, machine_*), Keycloak,
APISIX and the OTel collector. There is no kube-state-metrics and no node-exporter, so:
  - node CPU/memory come from the root cgroup of cAdvisor (id="/") and machine_* instead of node_*;
  - usage against limits comes from container_spec_* instead of kube_resourcequota.
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


GENERATED = {
    "platform-overview.json": platform_overview,
    "tenant-resources.json": tenant_resources,
    "containers-health.json": containers_health,
    "keycloak-jvm.json": keycloak_jvm,
    "observability-stack.json": observability_stack,
}

if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, fn in GENERATED.items():
        with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as f:
            json.dump(fn(), f, indent=2, ensure_ascii=False)
            f.write("\n")
    print(f"Generated {len(GENERATED)} Grafana dashboards into {os.path.normpath(OUT_DIR)}")
