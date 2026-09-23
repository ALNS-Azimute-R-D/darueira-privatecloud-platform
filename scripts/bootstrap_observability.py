#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Unified Observability & Telemetry Engine
OpenSearch Log Analytics, Fluent Bit, Prometheus, Grafana & Jaeger Bootstrapper
==============================================================================
"""

import sys
import os
import json
import time
import subprocess
import urllib.request
import urllib.error

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
OBS_DIR = os.path.join(PROJECT_ROOT, "platform", "kustomize", "base", "corpshared-obs")
APISIX_SCRIPT = os.path.join(SCRIPT_DIR, "bootstrap_apisix_routes.py")


def run_cmd(cmd, check=True):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and res.returncode != 0:
        print(f"    [!] Command failed: {cmd}\n    Stderr: {res.stderr.strip()}")
        raise RuntimeError(f"Command exited with code {res.returncode}: {res.stderr.strip()}")
    return res


def apply_observability_manifests():
    print("--> Applying Observability base manifests (OpenSearch, Fluent Bit, Prometheus, Grafana, Jaeger, OTel)...")
    run_cmd(f"microk8s kubectl apply -f {OBS_DIR}/")
    print("    [✓] Base observability manifests applied successfully")


def update_apisix_oidc_routes():
    print("--> Updating APISIX Gateway Ingress Routes with Keycloak OIDC Security...")
    # Port forward apisix gateway to seed routes
    pf = subprocess.Popen(
        "microk8s kubectl port-forward -n drr-corpshared-plat svc/apisix-gateway 9180:9180",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(2)
    try:
        run_cmd(f"python3 {APISIX_SCRIPT}")
        print("    [✓] APISIX Gateway routes secured with Keycloak OIDC authentication")
    finally:
        pf.terminate()
        pf.wait()


def wait_for_observability_rollout():
    print("--> Waiting for Observability Microservices Rollout and Health...")
    deployments = [
        "opensearch",
        "opensearch-dashboards",
        "prometheus",
        "grafana",
        "jaeger",
        "otel-collector"
    ]
    for dep in deployments:
        run_cmd(f"microk8s kubectl rollout status deployment/{dep} -n drr-corpshared-obs --timeout=90s")
        print(f"    [✓] Deployment '{dep}' is fully ready")


def opensearch_api(method, path, body=None):
    """Call the OpenSearch REST API from inside its pod (no Service exposure needed)."""
    cmd = ["microk8s", "kubectl", "exec", "-i", "-n", "drr-corpshared-obs", "deploy/opensearch", "--",
           "curl", "-s", "-X", method, f"localhost:9200/{path}"]
    if body is not None:
        cmd += ["-H", "Content-Type: application/json", "--data-binary", "@-"]
    res = subprocess.run(cmd, input=body, capture_output=True, text=True, check=True)
    reply = json.loads(res.stdout or "{}")
    # curl exits 0 on HTTP 4xx; OpenSearch reports failures in the body.
    if isinstance(reply, dict) and ("error" in reply or reply.get("failures")):
        raise RuntimeError(f"OpenSearch {method} {path} failed: {res.stdout}")
    return reply


def provision_opensearch_indices():
    """Index template (replicas 0, log_processed as flat_object) and ISM retention.

    Idempotent. A template only applies to indices created after it, so the
    existing daily indices are patched explicitly below.
    """
    print("--> Provisioning OpenSearch index template and ISM retention policy...")
    config_dir = os.path.join(OBS_DIR, "opensearch-index-config")

    def load(filename):
        with open(os.path.join(config_dir, filename)) as f:
            return f.read()

    opensearch_api("PUT", "_index_template/darueira-k8s-logs", load("index-template-darueira-k8s-logs.json"))
    print("    [✓] Index template darueira-k8s-logs")

    policy_path = "_plugins/_ism/policies/darueira-k8s-logs-retention"
    # ISM refuses a plain PUT over an existing policy; an update needs the
    # current seq_no/primary_term.
    try:
        current = opensearch_api("GET", policy_path)
        policy_path += f"?if_seq_no={current['_seq_no']}&if_primary_term={current['_primary_term']}"
    except RuntimeError:
        pass  # policy doesn't exist yet
    opensearch_api("PUT", policy_path, load("ism-policy-darueira-k8s-logs-retention.json"))
    print("    [✓] ISM policy darueira-k8s-logs-retention")

    # The policy's ism_template only auto-attaches to indices created from
    # now on; existing ones need an explicit add. On re-runs, indices that
    # are already managed come back as "failures" — expected, not an error.
    try:
        opensearch_api("POST", "_plugins/_ism/add/darueira-k8s-logs-*",
                       '{"policy_id": "darueira-k8s-logs-retention"}')
    except RuntimeError as e:
        reply = json.loads(str(e).split("failed: ", 1)[1])
        real = [f for f in reply.get("failed_indices", [])
                if "already has a policy" not in f["reason"]]
        if real or "failed_indices" not in reply:
            raise
    # Settings from the template, re-applied to existing indices (the
    # template covers new ones only):
    # - replicas 0: single-node cluster, replicas can never be allocated
    #   (cluster stays yellow).
    # - async translog + 30s refresh: every stateful service in the cluster
    #   shares one 5400 rpm HDD (/mnt/FileBuckets01). With the default
    #   per-request fsync, OpenSearch's single write thread sat in
    #   translog fsync while ~2000 bulk requests queued and log ingestion
    #   fell minutes behind. Losing up to 30s of logs on a crash is an
    #   acceptable trade for a log index.
    opensearch_api("PUT", "darueira-k8s-logs-*/_settings", json.dumps({"index": {
        "number_of_replicas": 0,
        "refresh_interval": "30s",
        "translog.durability": "async",
        "translog.sync_interval": "30s",
    }}))
    # ISM/job-scheduler system indices are created with 1 replica on first
    # use: same single-node problem. The ISM history index also rolls over
    # daily, so set its replica count at the cluster level too.
    opensearch_api("PUT", "_cluster/settings",
                   '{"persistent": {"plugins.index_state_management.history.number_of_replicas": 0}}')
    opensearch_api("PUT", ".opendistro-*/_settings?expand_wildcards=all",
                   '{"index": {"number_of_replicas": 0}}')
    # Map log_processed on existing indices too (adding a new field is
    # allowed). Otherwise, once Fluent Bit starts nesting under
    # log_processed, today's index would map it dynamically as a regular
    # object, re-exploding into hundreds of subfields and hitting the
    # 1000-field limit (rejecting logs) until the next daily index.
    # Done per index: a wildcard PUT is all-or-nothing, and old indices
    # already at the field limit (no longer written to, and soon deleted
    # by retention) would fail it for all.
    indices = opensearch_api("GET", "_cat/indices/darueira-k8s-logs-*?format=json&h=index")
    for index in sorted(i["index"] for i in indices):
        try:
            opensearch_api("PUT", f"{index}/_mapping",
                           '{"properties": {"log_processed": {"type": "flat_object"}}}')
        except RuntimeError as e:
            if "Limit of total fields" not in str(e):
                raise
            print(f"    [~] {index}: already at the field limit, log_processed not mapped (read-only history)")
    print("    [✓] Existing indices: retention attached, replicas 0, log_processed mapped")


def main():
    print("==================================================================")
    print("  Phase 12: Bootstrapping Unified Observability & Keycloak OIDC   ")
    print("==================================================================")

    apply_observability_manifests()
    update_apisix_oidc_routes()
    wait_for_observability_rollout()
    provision_opensearch_indices()

    print("\n[✓] Observability Stack & Keycloak OIDC Integration bootstrap completed successfully!")


if __name__ == "__main__":
    main()
