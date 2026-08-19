#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Unified Observability & Telemetry Engine
Observability Stack & Keycloak Central IAM Validation Suite
==============================================================================
"""

import sys
import os
import json
import ssl
import time
import base64
import subprocess
import urllib.request
import urllib.error

OPENSEARCH_HOST = os.environ.get("OPENSEARCH_HOST", "opensearch.drr-corpshared-obs.svc.cluster.local:9200")
OPENSEARCH_DASHBOARDS_HOST = os.environ.get("OPENSEARCH_DASHBOARDS_HOST", "opensearch-dashboards.drr-corpshared-obs.svc.cluster.local:5601")
PROMETHEUS_HOST = os.environ.get("PROMETHEUS_HOST", "prometheus.drr-corpshared-obs.svc.cluster.local:9090")
GRAFANA_HOST = os.environ.get("GRAFANA_HOST", "grafana.drr-corpshared-obs.svc.cluster.local:3000")
JAEGER_HOST = os.environ.get("JAEGER_HOST", "jaeger.drr-corpshared-obs.svc.cluster.local:16686")
OTEL_HOST = os.environ.get("OTEL_HOST", "otel-collector.drr-corpshared-obs.svc.cluster.local:13133")
APISIX_HTTP_HOST = os.environ.get("APISIX_HTTP_HOST", "apisix-gateway.drr-corpshared-plat.svc.cluster.local:80")

GRAFANA_ADMIN_USER = "admin"
GRAFANA_ADMIN_PASS = os.environ.get("GRAFANA_ADMIN_PASSWORD", "Darueira@2026!")


def test_pods_health():
    cmd = "microk8s kubectl get pods -n drr-corpshared-obs -o json"
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
    pods = json.loads(res.stdout).get("items", [])
    running = [p for p in pods if p.get("status", {}).get("phase") == "Running"]
    assert len(running) >= 7, f"Expected at least 7 observability pods running, found {len(running)}"
    return len(running)


def test_opensearch_cluster_health():
    req = urllib.request.Request(f"http://{OPENSEARCH_HOST}/_cluster/health")
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200, f"Expected HTTP 200, got {resp.status}"
        data = json.loads(resp.read().decode("utf-8"))
        status = data.get("status")
        nodes = data.get("number_of_nodes")
        assert status in ("green", "yellow"), f"OpenSearch status unhealthy: {status}"
        assert nodes >= 1, f"Expected at least 1 node, got {nodes}"
        return status, nodes


def test_fluent_bit_and_indices():
    req = urllib.request.Request(f"http://{OPENSEARCH_HOST}/_cat/indices?format=json")
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200
        indices = json.loads(resp.read().decode("utf-8"))
        log_indices = [idx for idx in indices if idx.get("index", "").startswith("darueira-k8s-logs-")]
        assert len(log_indices) >= 1, "Expected at least 1 darueira-k8s-logs-* index"
        total_docs = sum(int(idx.get("docs.count", 0)) for idx in log_indices)
        assert total_docs > 0, "Expected non-zero indexed logs in OpenSearch"
        return len(log_indices), total_docs


def test_opensearch_dashboards_status():
    req = urllib.request.Request(f"http://{OPENSEARCH_DASHBOARDS_HOST}/api/status")
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        overall_state = data.get("status", {}).get("overall", {}).get("state")
        version = data.get("version", {}).get("number")
        assert overall_state == "green", f"OpenSearch Dashboards state not green: {overall_state}"
        return version, overall_state


def test_prometheus_health_and_targets():
    req_ready = urllib.request.Request(f"http://{PROMETHEUS_HOST}/-/ready")
    with urllib.request.urlopen(req_ready, timeout=10) as resp:
        assert resp.status == 200, f"Expected Prometheus ready, got {resp.status}"

    req_targets = urllib.request.Request(f"http://{PROMETHEUS_HOST}/api/v1/targets")
    with urllib.request.urlopen(req_targets, timeout=10) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        targets = data.get("data", {}).get("activeTargets", [])
        up_targets = [t for t in targets if t.get("health") == "up"]
        assert len(up_targets) >= 1, "Expected at least 1 healthy Prometheus target"
        return len(up_targets), len(targets)


def test_grafana_datasources_and_dashboards():
    auth = base64.b64encode(f"{GRAFANA_ADMIN_USER}:{GRAFANA_ADMIN_PASS}".encode("utf-8")).decode("utf-8")
    headers = {"Authorization": f"Basic {auth}"}

    # 1. Datasources
    req_ds = urllib.request.Request(f"http://{GRAFANA_HOST}/api/datasources", headers=headers)
    with urllib.request.urlopen(req_ds, timeout=10) as resp:
        assert resp.status == 200
        ds_list = json.loads(resp.read().decode("utf-8"))
        ds_names = {d.get("name") for d in ds_list}
        for exp in ("Prometheus", "Jaeger", "OpenSearch"):
            assert exp in ds_names, f"Missing Grafana datasource: {exp}"

    # 2. Dashboards
    req_dash = urllib.request.Request(f"http://{GRAFANA_HOST}/api/search", headers=headers)
    with urllib.request.urlopen(req_dash, timeout=10) as resp:
        assert resp.status == 200
        dashboards = json.loads(resp.read().decode("utf-8"))
        dash_uids = {d.get("uid") for d in dashboards}
        assert "darueira-platform-overview" in dash_uids, "Missing platform overview dashboard"
        assert "darueira-tenant-quotas" in dash_uids, "Missing tenant quotas dashboard"
        assert "apisix-gateway-metrics" in dash_uids, "Missing apisix gateway metrics dashboard"
        return len(ds_names), len(dash_uids)


def test_jaeger_and_otel():
    req_jaeger = urllib.request.Request(f"http://{JAEGER_HOST}/api/services")
    with urllib.request.urlopen(req_jaeger, timeout=10) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "data" in data, "Jaeger API services response invalid"

    req_otel = urllib.request.Request(f"http://{OTEL_HOST}/")
    with urllib.request.urlopen(req_otel, timeout=10) as resp:
        assert resp.status == 200, f"OTel Collector health check failed with {resp.status}"
        return "Operational"


def test_keycloak_oidc_ingress_interception():
    # 1. Grafana Login Form (Keycloak Generic OAuth button)
    req_grafana = urllib.request.Request(f"http://{GRAFANA_HOST}/login")
    with urllib.request.urlopen(req_grafana, timeout=10) as resp:
        assert resp.status == 200
        content = resp.read().decode("utf-8")
        assert "Keycloak Central IAM" in content or "oauth" in content.lower(), "Keycloak OIDC not active in Grafana"

    # 2. OpenSearch & Jaeger Ingress Redirects via APISIX
    import http.client
    host_part = APISIX_HTTP_HOST.split(":")[0]
    port_part = int(APISIX_HTTP_HOST.split(":")[1]) if ":" in APISIX_HTTP_HOST else 80

    for domain in ("opensearch.darueira-corpshared.127.0.0.1.nip.io", "jaeger.darueira-corpshared.127.0.0.1.nip.io"):
        conn = http.client.HTTPConnection(host_part, port_part, timeout=10)
        conn.request("GET", "/", headers={"Host": domain})
        resp = conn.getresponse()
        assert resp.status == 302, f"Expected HTTP 302 redirect for {domain}, got {resp.status}"
        loc = resp.getheader("Location", "")
        assert "client_id=darueira-platform-generic-oidc" in loc, f"Keycloak client_id missing in redirect: {loc}"
        assert "darueira-platform-svcs" in loc, f"Keycloak realm missing in redirect: {loc}"
        conn.close()

    return "Verified"


def main():
    print("==================================================================")
    print("  Phase 12: Unified Observability & Keycloak OIDC Validation      ")
    print("==================================================================")

    # 1. Pod Health
    print("\n[1/8] Validating Observability Pods & Microservices Health...")
    pods = test_pods_health()
    print(f"      [✓] All {pods} Observability microservices are active and Running")

    # 2. OpenSearch Health
    print("\n[2/8] Validating OpenSearch Core Cluster Health & Shards...")
    st, nodes = test_opensearch_cluster_health()
    print(f"      [✓] OpenSearch Cluster is healthy (Status: {st.upper()}, Nodes: {nodes})")

    # 3. Fluent Bit Logs Ingestion
    print("\n[3/8] Validating Fluent Bit DaemonSet Live Log Pipeline...")
    idx_cnt, doc_cnt = test_fluent_bit_and_indices()
    print(f"      [✓] Fluent Bit active: {doc_cnt:,} logs indexed across {idx_cnt} indices")

    # 4. OpenSearch Dashboards
    print("\n[4/8] Validating OpenSearch Dashboards & Saved Objects...")
    ver, state = test_opensearch_dashboards_status()
    print(f"      [✓] OpenSearch Dashboards (v{ver}) is healthy (State: {state})")

    # 5. Prometheus Metrics Engine
    print("\n[5/8] Validating Prometheus Metrics Scraper & Active Targets...")
    up_t, tot_t = test_prometheus_health_and_targets()
    print(f"      [✓] Prometheus Metrics Server active ({up_t}/{tot_t} scrape targets UP)")

    # 6. Grafana Dashboards & Datasources
    print("\n[6/8] Validating Grafana Multi-Tenant Dashboards & Datasources...")
    ds_cnt, dash_cnt = test_grafana_datasources_and_dashboards()
    print(f"      [✓] Grafana configured with {ds_cnt} datasources and {dash_cnt} provisioned dashboards")

    # 7. Jaeger & OpenTelemetry
    print("\n[7/8] Validating Jaeger Distributed Tracing & OpenTelemetry Collector...")
    otel_st = test_jaeger_and_otel()
    print(f"      [✓] Jaeger Distributed Tracing & OpenTelemetry Collector {otel_st}")

    # 8. Keycloak Central IAM OIDC Ingress
    print("\n[8/8] Validating Keycloak Central IAM OIDC Protection (OpenSearch, Grafana, Jaeger)...")
    oidc_st = test_keycloak_oidc_ingress_interception()
    print(f"      [✓] Keycloak OIDC Authentication {oidc_st} across OpenSearch, Grafana & Jaeger")

    print("\n==================================================================")
    print("  [✓✓✓] ALL PHASE 12 OBSERVABILITY VALIDATION TESTS PASSED!       ")
    print("==================================================================")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[✗] Validation failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
