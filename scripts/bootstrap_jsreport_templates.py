#!/usr/bin/env python3
"""
==============================================================================
Script: scripts/bootstrap_jsreport_templates.py
Purpose: Idempotently loads the jsreport templates the BookAnything backend renders (Temporal activities) from
         platform/jsreport/templates/<name>.html into the jsreport store: handlebars engine, chrome-pdf recipe.
           geolocation-batch-summary  - executive PDF of a batch import
           geolocation-detail-report  - detail PDF of one GeoLocation (maps, flag, AI summary)
         A template that already exists is updated only when its content differs. Admin credentials come from the
         environment of the jsreport pod and are never printed.
Usage:   python3 scripts/bootstrap_jsreport_templates.py
Env:     KUBECTL (default "microk8s kubectl"), PLAT_NS (drr-corpshared-plat)
==============================================================================
"""

import json
import os
import pathlib
import shlex
import subprocess
import sys

KUBECTL = shlex.split(os.environ.get("KUBECTL", "microk8s kubectl"))
NS = os.environ.get("PLAT_NS", "drr-corpshared-plat")
DIR = pathlib.Path(__file__).resolve().parent.parent / "platform" / "jsreport" / "templates"
CHROME = {"format": "A4", "printBackground": True, "marginTop": "10mm", "marginBottom": "10mm",
          "marginLeft": "8mm", "marginRight": "8mm"}

CURL = 'curl -s -u "$extensions_authentication_admin_username:$extensions_authentication_admin_password" -H "Content-Type: application/json"'


def jsreport(method, path, body=None):
    cmd = [*KUBECTL, "-n", NS, "exec", "-i", "deploy/jsreport", "--", "sh", "-c",
           f'{CURL} -X {method} -w "\\n%{{http_code}}" \'http://localhost:5488{path}\' ' + ("-d @-" if body is not None else "")]
    res = subprocess.run(cmd, input=json.dumps(body) if body is not None else None, capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"[ERROR] kubectl exec: {res.stderr.strip()[:300]}")
    text, _, code = res.stdout.rpartition("\n")
    return int(code), (json.loads(text) if text.strip().startswith(("{", "[")) else text)


def main():
    for path in sorted(DIR.glob("*.html")):
        name, content = path.stem, path.read_text()
        code, found = jsreport("GET", f"/odata/templates?$filter=name%20eq%20%27{name}%27")
        if code != 200:
            sys.exit(f"[ERROR] listing templates: HTTP {code}")
        entity = {"name": name, "engine": "handlebars", "recipe": "chrome-pdf", "content": content, "chrome": CHROME}
        if not found["value"]:
            code, out = jsreport("POST", "/odata/templates", entity)
            print(f"    [+] {name}: created (HTTP {code})")
        elif found["value"][0].get("content") != content:
            code, out = jsreport("PATCH", f"/odata/templates(%27{found['value'][0]['_id']}%27)", entity)
            print(f"    [~] {name}: updated (HTTP {code})")
        else:
            print(f"    [=] {name}: already up to date")
            continue
        if code not in (200, 201, 204):
            sys.exit(f"[ERROR] {name}: HTTP {code} {str(out)[:200]}")


if __name__ == "__main__":
    main()
