"""Smoke test: can APISIX actually reach every upstream it routes to?

Reads every route (and named upstream) from the live APISIX Admin API, then
TCP-probes each distinct upstream node *from inside the apisix-gateway pod*
via an ephemeral busybox container. Probing with the gateway's own network
identity is the point: CiliumNetworkPolicy verdicts depend on the source
identity, so a probe from a laptop or a random pod proves nothing about
browser -> APISIX -> service traffic (see achados críticos #3 and #4 in
docs/runbooks/cilium-cni-migration.md, both missed by "no Hubble drops").

Exit code 0 when every upstream is reachable, 1 otherwise.

Note: each run adds one (terminated) ephemeral container to the gateway pod
spec. Kubernetes can't remove them; they go away on the next pod restart.
"""
import json
import os
import shlex
import subprocess
import sys
import time
import urllib.request

ADMIN_URL = os.environ.get("APISIX_ADMIN_URL", "http://127.0.0.1:9180/apisix/admin")
ADMIN_KEY = os.environ.get("APISIX_ADMIN_KEY", "edd1c9f034335f136f87ad84b625c8f1")
# May be a multi-word command, e.g. "microk8s kubectl" (Makefile fallback).
KUBECTL = shlex.split(os.environ.get("KUBECTL", "kubectl"))
GATEWAY_NS = "drr-corpshared-plat"
GATEWAY_SELECTOR = "app.kubernetes.io/name=apisix-gateway"
PROBE_IMAGE = "busybox:1.36"
PROBE_TIMEOUT_S = 4


def admin_get(path):
    req = urllib.request.Request(f"{ADMIN_URL}/{path}", headers={"X-API-KEY": ADMIN_KEY})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode()).get("list", [])


def upstream_nodes(upstream):
    nodes = (upstream or {}).get("nodes", {})
    if isinstance(nodes, list):
        return [f'{n["host"]}:{n["port"]}' for n in nodes]
    return list(nodes)


def collect_targets():
    """Map each upstream node (host:port) to the route ids that use it."""
    named = {u["value"]["id"]: u["value"] for u in admin_get("upstreams")}
    targets = {}
    for item in admin_get("routes"):
        route = item["value"]
        upstream = route.get("upstream") or named.get(route.get("upstream_id"), {})
        for node in upstream_nodes(upstream):
            targets.setdefault(node, []).append(route["id"])
    return targets


def kubectl(*args):
    return subprocess.check_output([*KUBECTL, *args], text=True).strip()


def probe_from_gateway(nodes):
    pod = kubectl("get", "pod", "-n", GATEWAY_NS, "-l", GATEWAY_SELECTOR,
                  "-o", "jsonpath={.items[0].metadata.name}")
    container = f"smoke-{int(time.time())}"
    checks = " ".join(
        f'(nc -z -w {PROBE_TIMEOUT_S} {n.rsplit(":", 1)[0]} {n.rsplit(":", 1)[1]} 2>/dev/null '
        f'&& echo "{n} OPEN" || echo "{n} CLOSED") &'
        for n in nodes
    )
    kubectl("debug", "-n", GATEWAY_NS, pod, f"--image={PROBE_IMAGE}", "--profile=restricted",
            "-q", f"--container={container}", "--", "sh", "-c", f"{checks} wait")

    # Probes run in parallel, so the whole batch takes ~PROBE_TIMEOUT_S plus image start.
    status_path = f'{{.status.ephemeralContainerStatuses[?(@.name=="{container}")].state.terminated.reason}}'
    for _ in range(60):
        if kubectl("get", "pod", "-n", GATEWAY_NS, pod, "-o", f"jsonpath={status_path}"):
            break
        time.sleep(2)
    else:
        sys.exit(f"probe container {container} on {pod} did not finish in time")

    results = {}
    for line in kubectl("logs", "-n", GATEWAY_NS, pod, "-c", container).splitlines():
        node, _, verdict = line.rpartition(" ")
        results[node] = verdict
    return pod, results


def main():
    targets = collect_targets()
    pod, results = probe_from_gateway(sorted(targets))

    failed = 0
    print(f"Probed {len(targets)} upstream nodes from {GATEWAY_NS}/{pod}\n")
    for node in sorted(targets, key=lambda n: (results.get(n) == "OPEN", n)):
        verdict = results.get(node, "UNKNOWN")
        if verdict != "OPEN":
            failed += 1
        routes = ", ".join(sorted(targets[node]))
        print(f"{verdict:8} {node:75} {routes}")

    print(f"\n{len(targets) - failed} OPEN, {failed} NOT REACHABLE")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
