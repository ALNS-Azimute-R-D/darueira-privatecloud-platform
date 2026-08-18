#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Enterprise Shared Services
Declarative Sonatype Nexus OSS IAM & Repository Bootstrapper
==============================================================================
"""

import sys
import os
import json
import base64
import time
import urllib.request
import urllib.error

NEXUS_HOST = os.environ.get("NEXUS_HOST", "nexus-oss.drr-corpshared-plat.svc.cluster.local:8081")
NEXUS_BASE_URL = f"http://{NEXUS_HOST}/service/rest/v1"
ADMIN_USER = "admin"
ADMIN_PASSWORD = os.environ.get("NEXUS_ADMIN_PASSWORD", "darueira-admin123")
LDAP_HOST = os.environ.get("LDAP_HOST", "authentik-ldap-outpost.drr-corpshared-plat.svc.cluster.local")
LDAP_PORT = int(os.environ.get("LDAP_PORT", "389"))
LDAP_BIND_DN = os.environ.get("LDAP_BIND_DN", "cn=akadmin,ou=users,dc=darueira,dc=local")
LDAP_BIND_SECRET = os.environ.get("LDAP_BIND_SECRET", "darueira-admin123")


def get_auth_header():
    # Try standard password first
    token = base64.b64encode(f"{ADMIN_USER}:{ADMIN_PASSWORD}".encode()).decode()
    req = urllib.request.Request(f"{NEXUS_BASE_URL}/status", headers={"Authorization": f"Basic {token}"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                return f"Basic {token}"
    except Exception:
        pass

    # Try initial admin password if present in file or environment
    init_pwd = os.environ.get("INITIAL_ADMIN_PASSWORD", "")
    if not init_pwd and os.path.exists("/nexus-data/admin.password"):
        try:
            with open("/nexus-data/admin.password", "r") as f:
                init_pwd = f.read().strip()
        except Exception:
            pass

    if init_pwd:
        token_init = base64.b64encode(f"{ADMIN_USER}:{init_pwd}".encode()).decode()
        # Change password to standard
        ch_req = urllib.request.Request(
            f"{NEXUS_BASE_URL}/security/users/admin/change-password",
            data=ADMIN_PASSWORD.encode(),
            headers={"Authorization": f"Basic {token_init}", "Content-Type": "text/plain"},
            method="PUT"
        )
        try:
            with urllib.request.urlopen(ch_req, timeout=5) as resp:
                print("    [✓] Initialized Nexus admin password to standard 'darueira-admin123'")
                return f"Basic {token}"
        except Exception as e:
            print(f"    Password change attempt error: {e}")

    return f"Basic {token}"


def configure_ldap(auth_hdr):
    print("--> Configuring Authentik LDAP Integration...")
    headers = {"Authorization": auth_hdr, "Content-Type": "application/json"}
    
    ldap_payload = {
        "name": "authentik-ldap",
        "protocol": "ldap",
        "useTrustStore": False,
        "host": LDAP_HOST,
        "port": LDAP_PORT,
        "searchBase": "dc=darueira,dc=local",
        "authScheme": "SIMPLE",
        "authUsername": LDAP_BIND_DN,
        "authPassword": LDAP_BIND_SECRET,
        "connectionTimeoutSeconds": 15,
        "connectionRetryDelaySeconds": 5,
        "maxIncidentsCount": 3,
        "userBaseDn": "ou=users",
        "userSubtree": True,
        "userObjectClass": "inetOrgPerson",
        "userIdAttribute": "cn",
        "userRealNameAttribute": "displayName",
        "userEmailAddressAttribute": "mail",
        "ldapGroupsAsRoles": True,
        "groupType": "dynamic",
        "groupBaseDn": "ou=groups",
        "groupSubtree": True,
        "userMemberOfAttribute": "memberOf"
    }

    # Check if exists
    get_req = urllib.request.Request(f"{NEXUS_BASE_URL}/security/ldap/authentik-ldap", headers=headers)
    try:
        with urllib.request.urlopen(get_req, timeout=5) as resp:
            # Update existing
            put_req = urllib.request.Request(
                f"{NEXUS_BASE_URL}/security/ldap/authentik-ldap",
                data=json.dumps(ldap_payload).encode(),
                headers=headers,
                method="PUT"
            )
            with urllib.request.urlopen(put_req, timeout=5) as p_resp:
                print("    [✓] Updated existing Authentik LDAP server configuration.")
                return
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"    LDAP get status error: {e.code}")

    # Create new
    post_req = urllib.request.Request(
        f"{NEXUS_BASE_URL}/security/ldap",
        data=json.dumps(ldap_payload).encode(),
        headers=headers,
        method="POST"
    )
    with urllib.request.urlopen(post_req, timeout=5) as resp:
        print("    [✓] Created Authentik LDAP server configuration.")


def configure_realms(auth_hdr):
    print("--> Activating Security Realms (NexusAuthenticatingRealm, LdapRealm, DockerToken)...")
    headers = {"Authorization": auth_hdr, "Content-Type": "application/json"}
    realms = ["NexusAuthenticatingRealm", "LdapRealm", "DockerToken"]
    req = urllib.request.Request(
        f"{NEXUS_BASE_URL}/security/realms/active",
        data=json.dumps(realms).encode(),
        headers=headers,
        method="PUT"
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        print(f"    [✓] Security realms activated: {realms}")


def configure_roles(auth_hdr):
    print("--> Configuring RBAC Roles for LDAP Group Mappings...")
    headers = {"Authorization": auth_hdr, "Content-Type": "application/json"}
    
    roles = [
        {
            "id": "role-platform-architect",
            "name": "Platform Architect (Enterprise Admin)",
            "description": "Full administrative permissions for platform architects",
            "privileges": ["nx-all"],
            "roles": ["nx-admin"]
        },
        {
            "id": "role-devops-engineer",
            "name": "DevOps Engineer (Release Manager)",
            "description": "Full registry and artifact deployment permissions",
            "privileges": ["nx-all"],
            "roles": ["nx-admin"]
        },
        {
            "id": "role-software-engineer",
            "name": "Software Engineer (Developer)",
            "description": "Read and write privileges for all artifact formats",
            "privileges": [
                "nx-repository-view-*-*-*",
                "nx-repository-admin-*-*-read",
                "nx-repository-admin-*-*-browse"
            ],
            "roles": []
        },
        {
            "id": "role-security-analyst",
            "name": "Security Analyst (Auditor)",
            "description": "Read-only and audit permissions for security scanning",
            "privileges": [
                "nx-repository-view-*-*-read",
                "nx-repository-view-*-*-browse"
            ],
            "roles": []
        }
    ]

    for role in roles:
        r_id = role["id"]
        # Check if role exists
        check_req = urllib.request.Request(f"{NEXUS_BASE_URL}/security/roles/{r_id}", headers=headers)
        try:
            with urllib.request.urlopen(check_req, timeout=5) as c_resp:
                put_req = urllib.request.Request(
                    f"{NEXUS_BASE_URL}/security/roles/{r_id}",
                    data=json.dumps(role).encode(),
                    headers=headers,
                    method="PUT"
                )
                with urllib.request.urlopen(put_req, timeout=5) as resp:
                    print(f"    [✓] Updated role: {r_id}")
                continue
        except urllib.error.HTTPError as e:
            if e.code != 404:
                print(f"    Role check warning for {r_id}: {e.code}")

        post_req = urllib.request.Request(
            f"{NEXUS_BASE_URL}/security/roles",
            data=json.dumps(role).encode(),
            headers=headers,
            method="POST"
        )
        try:
            with urllib.request.urlopen(post_req, timeout=5) as resp:
                print(f"    [✓] Created role: {r_id}")
        except urllib.error.HTTPError as e:
            print(f"    [✓] Role {r_id} already exists or code {e.code}")


def configure_repositories(auth_hdr):
    print("--> Configuring Corporate Repositories (Docker, Helm, NPM, PyPI)...")
    headers = {"Authorization": auth_hdr, "Content-Type": "application/json"}

    repos = [
        (
            "/repositories/docker/hosted",
            {
                "name": "docker-hosted",
                "online": True,
                "storage": {
                    "blobStoreName": "default",
                    "strictContentTypeValidation": True,
                    "writePolicy": "ALLOW"
                },
                "docker": {
                    "v1Enabled": False,
                    "forceBasicAuth": True,
                    "httpPort": 8082
                }
            }
        ),
        (
            "/repositories/helm/hosted",
            {
                "name": "helm-hosted",
                "online": True,
                "storage": {
                    "blobStoreName": "default",
                    "strictContentTypeValidation": True,
                    "writePolicy": "ALLOW"
                }
            }
        ),
        (
            "/repositories/npm/hosted",
            {
                "name": "npm-hosted",
                "online": True,
                "storage": {
                    "blobStoreName": "default",
                    "strictContentTypeValidation": True,
                    "writePolicy": "ALLOW"
                }
            }
        ),
        (
            "/repositories/pypi/hosted",
            {
                "name": "pypi-hosted",
                "online": True,
                "storage": {
                    "blobStoreName": "default",
                    "strictContentTypeValidation": True,
                    "writePolicy": "ALLOW"
                }
            }
        )
    ]

    for endpoint, payload in repos:
        r_name = payload["name"]
        req = urllib.request.Request(
            f"{NEXUS_BASE_URL}{endpoint}",
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                print(f"    [✓] Created repository: {r_name}")
        except urllib.error.HTTPError as e:
            if e.code in (400, 409):
                print(f"    [✓] Repository {r_name} already configured.")
            else:
                print(f"    [!] Repository {r_name} error: {e.code} {e.read().decode()}")


def main():
    print("==================================================================")
    print("  Bootstrapping Sonatype Nexus OSS for Darueira Cloud IAM        ")
    print("==================================================================")

    # 1. Wait for Nexus to be healthy
    print("--> Checking Nexus OSS Health...")
    for _ in range(15):
        try:
            with urllib.request.urlopen(f"{NEXUS_BASE_URL}/status", timeout=3) as resp:
                if resp.status == 200:
                    print("    Nexus OSS is healthy and responding.")
                    break
        except Exception:
            time.sleep(2)

    auth_hdr = get_auth_header()
    configure_ldap(auth_hdr)
    configure_realms(auth_hdr)
    configure_roles(auth_hdr)
    configure_repositories(auth_hdr)

    print("\n[✓] Sonatype Nexus OSS IAM & Repository bootstrap completed successfully!")


if __name__ == "__main__":
    main()
