#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Enterprise Shared Services
OpenFGA Fine-Grained Authorization (ReBAC) & Zero Trust Bootstrapper
==============================================================================
"""

import sys
import os
import json
import urllib.request
import urllib.error
import time

OPENFGA_HOST = os.environ.get("OPENFGA_HOST", "openfga.drr-corpshared-plat.svc.cluster.local:8080")
OPENFGA_BASE_URL = f"http://{OPENFGA_HOST}"
STORE_NAME = "darueira-rebac-store"

AUTH_MODEL = {
    "schema_version": "1.1",
    "type_definitions": [
        {"type": "user"},
        {
            "type": "organization",
            "relations": {
                "admin": {"this": {}},
                "member": {"this": {}}
            },
            "metadata": {
                "relations": {
                    "admin": {"directly_related_user_types": [{"type": "user"}]},
                    "member": {"directly_related_user_types": [{"type": "user"}]}
                }
            }
        },
        {
            "type": "project",
            "relations": {
                "parent_org": {"this": {}},
                "owner": {"this": {}},
                "maintainer": {
                    "union": {
                        "child": [
                            {"this": {}},
                            {"computedUserset": {"relation": "owner"}}
                        ]
                    }
                },
                "writer": {
                    "union": {
                        "child": [
                            {"this": {}},
                            {"computedUserset": {"relation": "maintainer"}}
                        ]
                    }
                },
                "reader": {
                    "union": {
                        "child": [
                            {"this": {}},
                            {"computedUserset": {"relation": "writer"}}
                        ]
                    }
                }
            },
            "metadata": {
                "relations": {
                    "parent_org": {"directly_related_user_types": [{"type": "organization"}]},
                    "owner": {"directly_related_user_types": [{"type": "user"}]},
                    "maintainer": {"directly_related_user_types": [{"type": "user"}]},
                    "writer": {"directly_related_user_types": [{"type": "user"}]},
                    "reader": {"directly_related_user_types": [{"type": "user"}]}
                }
            }
        },
        {
            "type": "environment",
            "relations": {
                "parent_project": {"this": {}},
                "admin": {"this": {}},
                "operator": {
                    "union": {
                        "child": [
                            {"this": {}},
                            {"computedUserset": {"relation": "admin"}}
                        ]
                    }
                },
                "viewer": {
                    "union": {
                        "child": [
                            {"this": {}},
                            {"computedUserset": {"relation": "operator"}}
                        ]
                    }
                },
                "can_read": {
                    "union": {
                        "child": [
                            {"computedUserset": {"relation": "viewer"}},
                            {"tupleToUserset": {"tupleset": {"relation": "parent_project"}, "computedUserset": {"relation": "reader"}}}
                        ]
                    }
                },
                "can_write": {
                    "union": {
                        "child": [
                            {"computedUserset": {"relation": "operator"}},
                            {"tupleToUserset": {"tupleset": {"relation": "parent_project"}, "computedUserset": {"relation": "writer"}}}
                        ]
                    }
                },
                "can_delete": {
                    "union": {
                        "child": [
                            {"computedUserset": {"relation": "admin"}},
                            {"tupleToUserset": {"tupleset": {"relation": "parent_project"}, "computedUserset": {"relation": "owner"}}}
                        ]
                    }
                }
            },
            "metadata": {
                "relations": {
                    "parent_project": {"directly_related_user_types": [{"type": "project"}]},
                    "admin": {"directly_related_user_types": [{"type": "user"}]},
                    "operator": {"directly_related_user_types": [{"type": "user"}]},
                    "viewer": {"directly_related_user_types": [{"type": "user"}]},
                    "can_read": {"directly_related_user_types": []},
                    "can_write": {"directly_related_user_types": []},
                    "can_delete": {"directly_related_user_types": []}
                }
            }
        }
    ]
}

RELATIONSHIP_TUPLES = [
    {"user": "user:andre.nascimento", "relation": "admin", "object": "organization:darueira"},
    {"user": "user:andre.nascimento", "relation": "admin", "object": "environment:acme-storefront-prod"},
    {"user": "user:andre.nascimento", "relation": "admin", "object": "environment:acme-logistics-prod"},
    {"user": "user:alice.developer", "relation": "member", "object": "organization:acme"},
    {"user": "user:alice.developer", "relation": "viewer", "object": "environment:acme-storefront-prod"},
    {"user": "user:bob.engineer", "relation": "member", "object": "organization:acme"},
    {"user": "user:bob.engineer", "relation": "operator", "object": "environment:acme-storefront-prod"},
    {"user": "user:carol.contractor", "relation": "member", "object": "organization:globex"},
    {"user": "organization:acme", "relation": "parent_org", "object": "project:acme-storefront"},
    {"user": "organization:acme", "relation": "parent_org", "object": "project:acme-logistics"},
    {"user": "organization:globex", "relation": "parent_org", "object": "project:globex-audit"},
    {"user": "project:acme-storefront", "relation": "parent_project", "object": "environment:acme-storefront-prod"},
    {"user": "project:acme-logistics", "relation": "parent_project", "object": "environment:acme-logistics-prod"},
    {"user": "project:globex-audit", "relation": "parent_project", "object": "environment:globex-audit-prod"}
]


def get_or_create_store():
    req = urllib.request.Request(f"{OPENFGA_BASE_URL}/stores")
    with urllib.request.urlopen(req, timeout=10) as resp:
        stores_data = json.loads(resp.read().decode())
        for s in stores_data.get("stores", []):
            if s.get("name") == STORE_NAME:
                print(f"    [✓] Reusing existing OpenFGA Store: {s.get('id')}")
                return s.get("id")

    req_create = urllib.request.Request(
        f"{OPENFGA_BASE_URL}/stores",
        data=json.dumps({"name": STORE_NAME}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req_create, timeout=10) as resp:
        s = json.loads(resp.read().decode())
        print(f"    [✓] Created OpenFGA Store: {s.get('id')}")
        return s.get("id")


def bootstrap_auth_model(store_id):
    req = urllib.request.Request(
        f"{OPENFGA_BASE_URL}/stores/{store_id}/authorization-models",
        data=json.dumps(AUTH_MODEL).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
        model_id = data.get("authorization_model_id")
        print(f"    [✓] Registered Authorization Model: {model_id}")
        return model_id


def bootstrap_tuples(store_id):
    payload = {
        "writes": {
            "tuple_keys": RELATIONSHIP_TUPLES
        }
    }
    req = urllib.request.Request(
        f"{OPENFGA_BASE_URL}/stores/{store_id}/write",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"    [✓] Written {len(RELATIONSHIP_TUPLES)} relationship tuples into OpenFGA Store.")
    except urllib.error.HTTPError as e:
        if e.code == 400 and "cannot write a tuple which already exists" in e.read().decode():
            print(f"    [✓] Relationship tuples already written.")
        else:
            raise


def main():
    print("==================================================================")
    print("  Bootstrapping OpenFGA ReBAC Fine-Grained Authorization Engine   ")
    print("==================================================================")

    store_id = get_or_create_store()
    bootstrap_auth_model(store_id)
    bootstrap_tuples(store_id)

    print("\n[✓] OpenFGA ReBAC bootstrap completed successfully!")


if __name__ == "__main__":
    main()
