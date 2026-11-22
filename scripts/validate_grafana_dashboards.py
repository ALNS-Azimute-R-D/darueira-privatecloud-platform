#!/usr/bin/env python3
"""
validate_grafana_dashboards.py
Checks every dashboard in platform/kustomize/base/corpshared-obs/dashboards/grafana/ before it is applied:
  - structure: unique panel ids, panels inside the 24-column grid, every panel with a query has a datasource;
  - every PromQL expression is evaluated on Prometheus. An expression that Prometheus rejects is an ERROR (exit code 1).
    One that returns no series is a WARNING: it is legitimate for "what is broken" panels (no OOM kills, no restarts), but a
    panel that is empty by mistake (a metric that does not exist) looks exactly like that, so read the list.

Usage:   kubectl -n drr-corpshared-obs port-forward svc/prometheus 9090:9090 &
         python3 scripts/validate_grafana_dashboards.py            (PROM_URL overrides http://127.0.0.1:9090)
"""

import glob
import json
import os
import re
import sys
import urllib.parse
import urllib.request

PROM_URL = os.environ.get("PROM_URL", "http://127.0.0.1:9090")
DASH_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "platform", "kustomize", "base",
                        "corpshared-obs", "dashboards", "grafana")


def substitute(expr):
    """Replaces Grafana variables with a value Prometheus understands."""
    expr = expr.replace("$__rate_interval", "5m").replace("$__interval", "1m").replace("${__interval}", "1m")
    return re.sub(r"\$\{?(ns|namespace|tenant|pg)\}?", ".*", expr)


def evaluate(expr):
    url = f"{PROM_URL}/api/v1/query?" + urllib.parse.urlencode({"query": substitute(expr)})
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            body = json.load(resp)
    except urllib.error.HTTPError as e:
        return "ERROR", e.read().decode()[:160]
    except Exception as e:  # connection problems are errors too
        return "ERROR", str(e)[:160]
    if body.get("status") != "success":
        return "ERROR", str(body)[:160]
    return ("OK" if body["data"]["result"] else "EMPTY"), len(body["data"]["result"])


def walk(panels):
    for p in panels:
        yield p
        yield from walk(p.get("panels", []))


def main():
    files = sorted(glob.glob(os.path.join(DASH_DIR, "*.json")))
    if not files:
        sys.exit(f"no dashboards in {DASH_DIR}")
    errors = warnings = checked = 0
    for path in files:
        d = json.load(open(path, encoding="utf-8"))
        name = os.path.basename(path)
        panels = list(walk(d.get("panels", [])))
        ids = [p["id"] for p in panels if "id" in p]
        print(f"== {name}  uid={d.get('uid')}  panels={len(panels)}  variables={[v['name'] for v in d.get('templating', {}).get('list', [])]}")
        if len(ids) != len(set(ids)):
            print("   ERROR duplicate panel ids"); errors += 1
        for p in panels:
            gp = p.get("gridPos")
            if p.get("type") != "row" and gp and gp["x"] + gp["w"] > 24:
                print(f"   ERROR panel '{p.get('title')}' leaves the 24-column grid"); errors += 1
            for t in p.get("targets", []):
                expr = t.get("expr")
                if not expr:
                    continue
                if not (t.get("datasource") or p.get("datasource")):
                    print(f"   ERROR panel '{p.get('title')}' has a query and no datasource"); errors += 1
                status, info = evaluate(expr)
                checked += 1
                if status == "ERROR":
                    errors += 1
                    print(f"   ERROR  {p.get('title')[:44]:44s} {info}")
                elif status == "EMPTY":
                    warnings += 1
                    print(f"   EMPTY  {p.get('title')[:44]:44s} {expr[:90]}")
    print(f"\n{checked} queries evaluated: {errors} error(s), {warnings} empty")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
