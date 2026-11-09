#!/usr/bin/env python3
"""
==============================================================================
Script: scripts/bootstrap_sso_central_services.py
Purpose: Idempotent re-wiring of "sign in with the central Keycloak" on the services whose own state is lost
         when their database or volume is recreated (for instance after a disk crash). Nothing is printed
         that is a secret; secrets are read from Keycloak and handed straight to the service.

         1. Forgejo  : OAuth2 auth source `keycloak-oidc` (client `forgejo-git`). Created, or its secret
                       updated when it already exists.
         2. jsreport : it only accepts a Keycloak login for a user that already exists in its own store with
                       the same `preferred_username`. The users in JSREPORT_USERS are created (admin) when missing.
         3. MinIO    : when the log shows it gave up on OpenID at start-up (DNS not ready yet, so the
                       "Keycloak Central IAM" button is missing), the deployment is restarted.

         Not automated on purpose: Grafana answers `user already exists` when a stale user holds the same
         e-mail under an old Keycloak `sub`. Delete that one user by hand (Administration > Users); dashboards
         are provisioned from ConfigMaps and are not affected.

         The shared client `darueira-platform-generic-oidc` (Grafana, ArgoCD, Temporal UI, NiFi, jsreport,
         MinIO) keeps the secret from the manifests; compare with `--check-shared-secret`.

Usage:   python3 scripts/bootstrap_sso_central_services.py [--check-shared-secret]
Env:     KUBECTL (default "microk8s kubectl"), KEYCLOAK_ADMIN_USER / KEYCLOAK_ADMIN_PASS (admin / admin123-dev),
         CENTRAL_REALM (darueira-platform-svcs), PLAT_NS (drr-corpshared-plat),
         JSREPORT_USERS (comma separated, default andre.nascimento)
==============================================================================
"""

import base64
import json
import os
import secrets
import shlex
import subprocess
import sys
import time
import urllib.parse
import urllib.request

KUBECTL = shlex.split(os.environ.get("KUBECTL", "microk8s kubectl"))
NS = os.environ.get("PLAT_NS", "drr-corpshared-plat")
REALM = os.environ.get("CENTRAL_REALM", "darueira-platform-svcs")
KC_USER = os.environ.get("KEYCLOAK_ADMIN_USER", "admin")
KC_PASS = os.environ.get("KEYCLOAK_ADMIN_PASS", "admin123-dev")
JSREPORT_USERS = [u.strip() for u in os.environ.get("JSREPORT_USERS", "andre.nascimento").split(",") if u.strip()]
ISSUER = "https://keycloak.darueira-corpshared.127.0.0.1.nip.io/realms/" + REALM
PORT = 18081


def kube(*args, check=True, ns=NS):
    res = subprocess.run([*KUBECTL, "-n", ns, *args], capture_output=True, text=True)
    if check and res.returncode != 0:
        sys.exit(f"[ERROR] kubectl {' '.join(args[:3])}...: {res.stderr.strip()[:300]}")
    return res


class KeycloakPortForward:
    """Central Keycloak is not exposed on the host without the gateway proxy; a port-forward is enough."""

    def __enter__(self):
        self.proc = subprocess.Popen([*KUBECTL, "-n", NS, "port-forward", "svc/keycloak", f"{PORT}:8080"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(20):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/realms/master", timeout=2)
                return self
            except Exception:
                time.sleep(1)
        self.proc.kill()
        sys.exit("[ERROR] could not reach the central Keycloak through a port-forward")

    def __exit__(self, *exc):
        self.proc.terminate()


def kc(path, data=None, token=None):
    headers = {}
    body = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    with urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", body, headers), timeout=20) as r:
        return json.loads(r.read())


def client_secret(token, client_id):
    found = kc(f"/admin/realms/{REALM}/clients?clientId={urllib.parse.quote(client_id)}", token=token)
    if not found:
        sys.exit(f"[ERROR] client '{client_id}' does not exist in realm {REALM}")
    return kc(f"/admin/realms/{REALM}/clients/{found[0]['id']}/client-secret", token=token)["value"]


def forgejo(token):
    print("--> 1. Forgejo OAuth2 source 'keycloak-oidc'")
    secret = client_secret(token, "forgejo-git")
    listing = kube("exec", "deploy/forgejo-git", "-c", "forgejo", "--", "forgejo", "admin", "auth", "list").stdout
    source_id = next((ln.split()[0] for ln in listing.splitlines() if "keycloak-oidc" in ln), None)
    common = ["--provider", "openidConnect", "--key", "forgejo-git", "--secret", secret,
              "--auto-discover-url", f"{ISSUER}/.well-known/openid-configuration", "--scopes", "openid profile email"]
    if source_id:
        kube("exec", "deploy/forgejo-git", "-c", "forgejo", "--", "forgejo", "admin", "auth", "update-oauth",
             "--id", source_id, *common)
        print(f"    [=] source {source_id} already existed; secret refreshed")
    else:
        kube("exec", "deploy/forgejo-git", "-c", "forgejo", "--", "forgejo", "admin", "auth", "add-oauth",
             "--name", "keycloak-oidc", *common)
        print("    [+] source created")


JSREPORT_SH = r'''
AUTH="$extensions_authentication_admin_username:$extensions_authentication_admin_password"
U="$1"
if curl -s -u "$AUTH" "http://localhost:5488/odata/users?\$select=username" | grep -q "\"username\":\"$U\""; then
  echo "exists"; exit 0
fi
PW=$(head -c 24 /dev/urandom | base64 | tr -d "/+=")
code=$(curl -s -o /dev/null -w "%{http_code}" -u "$AUTH" -H "Content-Type: application/json" -X POST \
  http://localhost:5488/odata/users -d "{\"username\":\"$U\",\"password\":\"$PW\",\"isAdmin\":true}")
echo "created:$code"
'''


def jsreport():
    print("--> 2. jsreport users (the Keycloak login needs a user with the same name)")
    for user in JSREPORT_USERS:
        out = kube("exec", "deploy/jsreport", "--", "sh", "-c", JSREPORT_SH, "sh", user).stdout.strip()
        print(f"    [{'=' if out == 'exists' else '+'}] {user}: {out}")


def minio():
    print("--> 3. MinIO OpenID start-up")
    log = kube("logs", "deploy/central-minio", "-c", "minio", "--tail=60", check=False).stdout
    if "Unable to initialize OpenID" in log:
        kube("rollout", "restart", "deploy/central-minio")
        kube("rollout", "status", "deploy/central-minio", "--timeout=180s")
        print("    [+] OpenID had failed at start-up; deployment restarted")
    else:
        print("    [=] no OpenID error in the log")


def check_shared_secret(token):
    """Compares the Keycloak secret of the shared client with the copies in the manifests, printing only yes/no."""
    print("--> Shared client 'darueira-platform-generic-oidc' secret check")
    wanted = client_secret(token, "darueira-platform-generic-oidc")
    for ns, kind in (("drr-corpshared-plat", "deploy"), ("drr-corpshared-plat", "cm"), ("drr-corpshared-obs", "deploy"),
                     ("drr-corpshared-mgmt", "secret"), ("drr-corpshared-mgmt", "cm")):
        text = kube("get", kind, "-o", "yaml", ns=ns, check=False).stdout
        # Secret values are stored base64 encoded
        needle = base64.b64encode(wanted.encode()).decode() if kind == "secret" else wanted
        print(f"    {ns}/{kind}: {'contains the current secret' if needle in text else 'no copy found'}")


def main():
    with KeycloakPortForward():
        token = kc("/realms/master/protocol/openid-connect/token",
                   {"client_id": "admin-cli", "username": KC_USER, "password": KC_PASS, "grant_type": "password"})["access_token"]
        if "--check-shared-secret" in sys.argv:
            check_shared_secret(token)
            return
        forgejo(token)
    jsreport()
    minio()
    print("Done. Grafana: if it answers `user already exists`, delete the stale user (see the header).")


if __name__ == "__main__":
    main()
