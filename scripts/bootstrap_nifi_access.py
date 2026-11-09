#!/usr/bin/env python3
"""
==============================================================================
Script: scripts/bootstrap_nifi_access.py
Purpose: Idempotently grants NiFi access after its security files were lost or recreated:
           - the node certificate identity used by scripts/apply_nifi_*.py (mTLS from inside the pod), and
           - the OIDC administrator (INITIAL_ADMIN_IDENTITY) the same canvas policies on the root process group,
         by editing users.xml / authorizations.xml on the PVC (`data/conf`, restored at every start) and restarting
         NiFi. Policies granted: /flow R, /controller R/W, /tenants R/W, /policies R/W, /restricted-components W,
         /process-groups/<root> R/W and /data/process-groups/<root> R/W. Nothing secret is read or printed.
Usage:   python3 scripts/bootstrap_nifi_access.py [--no-restart]
Env:     KUBECTL (default "microk8s kubectl"), PLAT_NS (drr-corpshared-plat),
         NIFI_ADMIN (andre.nascimento),
         NIFI_CERT_IDENTITY ("OU=Security Platform, O=Darueira Enterprise Private Cloud, CN=*.darueira-corpshared.127.0.0.1.nip.io")
==============================================================================
"""

import gzip
import json
import os
import shlex
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

KUBECTL = shlex.split(os.environ.get("KUBECTL", "microk8s kubectl"))
NS = os.environ.get("PLAT_NS", "drr-corpshared-plat")
ADMIN = os.environ.get("NIFI_ADMIN", "andre.nascimento")
CERT = os.environ.get("NIFI_CERT_IDENTITY",
                      "OU=Security Platform, O=Darueira Enterprise Private Cloud, CN=*.darueira-corpshared.127.0.0.1.nip.io")
CONF = "/opt/nifi/nifi-current/data/conf"
NS_UUID = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def kube(*args, stdin=None):
    res = subprocess.run([*KUBECTL, "-n", NS, *args], input=stdin, capture_output=True)
    if res.returncode != 0:
        sys.exit(f"[ERROR] kubectl {' '.join(args[:4])}...: {res.stderr.decode()[:300]}")
    return res.stdout


def nifi(*cmd, stdin=None):
    return kube("exec", "-i", "deploy/apache-nifi", "-c", "nifi", "--", *cmd, stdin=stdin)


def live_root_id():
    """The canvas root group id the API uses is the flow's instanceIdentifier, not its `identifier`."""
    flow = json.loads(gzip.decompress(nifi("cat", f"{CONF}/flow.json.gz")))["rootGroup"]
    return flow.get("instanceIdentifier") or flow["identifier"]


def main():
    root_id = live_root_id()
    users = ET.fromstring(nifi("cat", f"{CONF}/users.xml"))
    policies = ET.fromstring(nifi("cat", f"{CONF}/authorizations.xml"))

    user_ids = {}
    container = users.find("users")
    for u in container:
        user_ids[u.get("identity")] = u.get("identifier")
    if ADMIN not in user_ids:
        sys.exit(f"[ERROR] admin '{ADMIN}' is not in users.xml; log in once through Keycloak first")
    if CERT not in user_ids:
        ident = str(uuid.uuid5(NS_UUID, "nifi-user:" + CERT))
        ET.SubElement(container, "user", identifier=ident, identity=CERT)
        user_ids[CERT] = ident
        print(f"    [+] user {CERT}")

    wanted = [("/flow", "R"), ("/controller", "R"), ("/controller", "W"), ("/tenants", "R"), ("/tenants", "W"),
              ("/policies", "R"), ("/policies", "W"), ("/restricted-components", "W"),
              (f"/process-groups/{root_id}", "R"), (f"/process-groups/{root_id}", "W"),
              (f"/data/process-groups/{root_id}", "R"), (f"/data/process-groups/{root_id}", "W")]
    listing = policies.find("policies")
    existing = {(p.get("resource"), p.get("action")): p for p in listing}
    changed = 0
    for res, act in wanted:
        pol = existing.get((res, act))
        if pol is None:
            pol = ET.SubElement(listing, "policy", identifier=str(uuid.uuid5(NS_UUID, f"nifi-policy:{res}:{act}")),
                                resource=res, action=act)
        have = {x.get("identifier") for x in pol.findall("user")}
        for ident in (user_ids[ADMIN], user_ids[CERT]):
            if ident not in have:
                ET.SubElement(pol, "user", identifier=ident)
                changed += 1
    if not changed and CERT in user_ids and "--force" not in sys.argv:
        print("    [=] nothing to change")
        return
    for name, tree in (("users.xml", users), ("authorizations.xml", policies)):
        ET.indent(tree)
        data = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + ET.tostring(tree)
        nifi("sh", "-c", f"cat > {CONF}/{name}", stdin=data)
    print(f"    [+] {changed} grants written to the PVC (root group {root_id})")
    if "--no-restart" not in sys.argv:
        kube("rollout", "restart", "deploy/apache-nifi")
        kube("rollout", "status", "deploy/apache-nifi", "--timeout=300s")
        print("    [✓] NiFi restarted")


if __name__ == "__main__":
    main()
