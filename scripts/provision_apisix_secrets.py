#!/usr/bin/env python3
"""
Creates the Secret `apisix-secrets` (namespace drr-corpshared-plat) that scripts/bootstrap_apisix_routes.py reads, so that no
credential is a literal in Git (backlog item 51).

Keys:
  admin-key           APISIX Admin API key
  oidc-client-secret  secret of the Keycloak client `darueira-platform-generic-oidc` used by the OIDC routes
  session-opensearch  cookie-session secret of the OpenSearch Dashboards route (random, free to change)
  session-jaeger      cookie-session secret of the Jaeger route (random, free to change)

Idempotent: keys that already exist are kept. Missing keys are filled so that NOTHING breaks:
  - admin-key and oidc-client-secret come from the environment (APISIX_ADMIN_KEY, OIDC_CLIENT_SECRET) when set; otherwise from
    the values already live in the cluster (the apisix-config ConfigMap and the Secret grafana-credentials, which holds the same
    Keycloak client secret). Nothing is read from the repository.
  - the session secrets are generated here.
Values are never printed, never put on a command line and never written to a file; the Secret is created (not applied).

Usage: python3 scripts/provision_apisix_secrets.py [--rotate-sessions]
"""
import base64
import json
import os
import re
import secrets
import string
import subprocess
import sys

NS = "drr-corpshared-plat"
SECRET = "apisix-secrets"


def kubectl(*args, stdin=None, check=True):
    return subprocess.run(["kubectl", *args], input=stdin, capture_output=True, text=True, check=check)


def existing():
    r = kubectl("-n", NS, "get", "secret", SECRET, "-o", "json", check=False)
    if r.returncode != 0:
        return {}
    return {k: base64.b64decode(v).decode() for k, v in (json.loads(r.stdout).get("data") or {}).items()}


def live_admin_key():
    cm = kubectl("-n", NS, "get", "cm", "apisix-config", "-o", "json").stdout
    conf = next(iter(json.loads(cm)["data"].values()))
    m = re.search(r"admin_key:\s*\n\s*-\s*name:\s*admin\s*\n\s*key:\s*(\S+)", conf)
    if not m:
        sys.exit("could not find the admin key in the apisix-config ConfigMap")
    return m.group(1)


def live_oidc_client_secret():
    r = kubectl("-n", "drr-corpshared-obs", "get", "secret", "grafana-credentials", "-o", "jsonpath={.data.oauth-client-secret}", check=False)
    if r.returncode != 0 or not r.stdout:
        sys.exit("OIDC_CLIENT_SECRET is not set and the Secret grafana-credentials has no oauth-client-secret")
    return base64.b64decode(r.stdout).decode()


def random_secret(n=48):
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(n))


def main():
    values = existing()
    before = dict(values)
    if "admin-key" not in values:
        values["admin-key"] = os.environ.get("APISIX_ADMIN_KEY") or live_admin_key()
    if "oidc-client-secret" not in values:
        values["oidc-client-secret"] = os.environ.get("OIDC_CLIENT_SECRET") or live_oidc_client_secret()
    for key in ("session-opensearch", "session-jaeger"):
        if key not in values or "--rotate-sessions" in sys.argv:
            values[key] = random_secret()
    if values == before:
        print(f"[=] Secret {SECRET} already complete: {sorted(values)}")
        return
    args = ["-n", NS, "create", "secret", "generic", SECRET]
    # Values travel through process substitution-free temporary pipes: one --from-file per key, read from /dev/fd.
    r, w = zip(*[os.pipe() for _ in values])
    try:
        for (key, val), wfd in zip(values.items(), w):
            os.write(wfd, val.encode())
            os.close(wfd)
        fds = {key: rfd for key, rfd in zip(values, r)}
        proc = subprocess.run(["kubectl", *(["-n", NS, "delete", "secret", SECRET, "--ignore-not-found"])], capture_output=True, text=True)
        proc = subprocess.run(["kubectl", *args, *[f"--from-file={k}=/dev/fd/{fd}" for k, fd in fds.items()]],
                              pass_fds=list(fds.values()), capture_output=True, text=True)
        if proc.returncode != 0:
            sys.exit("could not create the Secret: " + proc.stderr.strip()[:200])
    finally:
        for fd in r:
            try:
                os.close(fd)
            except OSError:
                pass
    kubectl("-n", NS, "label", "secret", SECRET, "app.kubernetes.io/name=apisix", "darueira.io/tier=enterprise-shared", "--overwrite")
    added = sorted(set(values) - set(before))
    print(f"[+] Secret {SECRET} written; new keys: {added or 'none (sessions rotated)'}")


if __name__ == "__main__":
    main()
