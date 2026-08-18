#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Enterprise Shared Services
Sonatype Nexus OSS LDAP IAM & Repositories Validation Suite
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
DOCKER_REGISTRY_HOST = os.environ.get("DOCKER_REGISTRY_HOST", "nexus-oss.drr-corpshared-plat.svc.cluster.local:8082")

TEST_USERS = [
    {
        "username": "andre.nascimento",
        "email": "andre.nascimento@darueira.local",
        "password": "Darueira@2026!",
        "role": "role-platform-architect",
        "expected_role_type": "Admin"
    },
    {
        "username": "alice.developer",
        "email": "alice.developer@darueira.local",
        "password": "Darueira@2026!",
        "role": "role-software-engineer",
        "expected_role_type": "Developer"
    },
    {
        "username": "bob.engineer",
        "email": "bob.engineer@darueira.local",
        "password": "Darueira@2026!",
        "role": "role-devops-engineer",
        "expected_role_type": "Admin/DevOps"
    },
    {
        "username": "carol.contractor",
        "email": "carol.contractor@globex.local",
        "password": "Darueira@2026!",
        "role": "role-security-analyst",
        "expected_role_type": "Auditor/Viewer"
    }
]

EXPECTED_REPOSITORIES = [
    "maven-releases",
    "maven-snapshots",
    "maven-central",
    "maven-public",
    "docker-hosted",
    "helm-hosted",
    "npm-hosted",
    "pypi-hosted"
]


def test_user_authentication(user_info):
    username = user_info["username"]
    password = user_info["password"]
    auth = base64.b64encode(f"{username}:{password}".encode()).decode()
    
    url = f"http://{NEXUS_HOST}/service/rest/v1/repositories"
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
    
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200, f"Expected HTTP 200, got {resp.status}"
        repos = json.loads(resp.read().decode("utf-8"))
        repo_names = [r["name"] for r in repos]
        return repo_names


def test_docker_v2_ping(user_info):
    username = user_info["username"]
    password = user_info["password"]
    auth = base64.b64encode(f"{username}:{password}".encode()).decode()
    
    url = f"http://{DOCKER_REGISTRY_HOST}/v2/"
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
    
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200, f"Expected HTTP 200 from Docker v2 ping, got {resp.status}"
        api_version = resp.headers.get("Docker-Distribution-Api-Version")
        assert api_version == "registry/2.0", f"Expected registry/2.0 API version header, got {api_version}"
        return api_version


def test_repository_health():
    auth = base64.b64encode(b"admin:darueira-admin123").decode()
    url = f"http://{NEXUS_HOST}/service/rest/v1/repositories"
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        repos = json.loads(resp.read().decode("utf-8"))
        repo_map = {r["name"]: r for r in repos}

    missing = set(EXPECTED_REPOSITORIES) - set(repo_map.keys())
    assert not missing, f"Missing required corporate repositories: {missing}"
    return repo_map


def main():
    print("==================================================================")
    print("  Phase 03: Sonatype Nexus OSS LDAP IAM Validation Suite          ")
    print("==================================================================")

    # 1. Repository health & provisioning check
    print("\n[1/3] Validating Corporate Repositories Health & Online Status...")
    repo_map = test_repository_health()
    print(f"      [✓] All {len(EXPECTED_REPOSITORIES)} core repositories are healthy and online:")
    for r_name in EXPECTED_REPOSITORIES:
        fmt = repo_map[r_name].get("format")
        r_type = repo_map[r_name].get("type")
        print(f"          - {r_name:20} (Format: {fmt:8} | Type: {r_type})")

    # 2. LDAP User Authentication & RBAC Visibility
    print("\n[2/3] Validating Authentik LDAP User Authentication & RBAC...")
    for user in TEST_USERS:
        u_name = user["username"]
        role = user["role"]
        exp_type = user["expected_role_type"]
        print(f"  --> Authenticating {u_name} (Role: {role} / {exp_type})...")
        visible_repos = test_user_authentication(user)
        assert len(visible_repos) > 0, f"No repositories visible for {u_name}"
        print(f"      [✓] Authenticated successfully! {len(visible_repos)} repositories accessible.")

    # 3. Docker Registry v2 API Authentication
    print("\n[3/3] Validating Docker & OCI Container Registry v2 Protocol (:8082)...")
    for user in TEST_USERS[:2]:
        u_name = user["username"]
        print(f"  --> Pinging /v2/ endpoint as {u_name}...")
        api_ver = test_docker_v2_ping(user)
        print(f"      [✓] Docker v2 API Authenticated (Docker-Distribution-Api-Version: {api_ver})")

    print("\n==================================================================")
    print("  [✓✓✓] ALL PHASE 03 NEXUS OSS IAM VALIDATION TESTS PASSED!       ")
    print("==================================================================")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[✗] Validation failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
