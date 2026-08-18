#!/usr/bin/env python3
"""
==============================================================================
Script: scripts/bootstrap_stalwart_iam.py
Purpose: Idempotently configure Stalwart Mail Server for Corporate IAM:
         - Setup Corporate Domains (darueira.local, globex.local)
         - Setup System Settings & Default Domain
         - Setup Authentik LDAP Directory Provider
         - Setup Keycloak OIDC Authentication Provider
         - Setup Authentication Singleton & Role Mapping (User, Group, Admin)
         - Setup Console Tracer for Observability
         - Sync and Grant User Account Roles
==============================================================================
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import base64

STALWART_JMAP_URL = os.environ.get("STALWART_JMAP_URL", "http://stalwart-mail.drr-corpshared-plat.svc.cluster.local:8080/jmap/")
STALWART_ADMIN_USER = os.environ.get("STALWART_ADMIN_USER", "admin")
STALWART_ADMIN_PASS = os.environ.get("STALWART_ADMIN_PASS", "darueira-admin123")

KEYCLOAK_ISSUER_URL = os.environ.get("KEYCLOAK_ISSUER_URL", "https://keycloak.darueira-corpshared.127.0.0.1.nip.io/realms/darueira-platform-svcs")
LDAP_URL = os.environ.get("LDAP_URL", "ldap://authentik-ldap-outpost.drr-corpshared-plat.svc.cluster.local:389")
LDAP_BASE_DN = os.environ.get("LDAP_BASE_DN", "dc=darueira,dc=local")
LDAP_BIND_DN = os.environ.get("LDAP_BIND_DN", "cn=akadmin,ou=users,dc=darueira,dc=local")
LDAP_BIND_SECRET = os.environ.get("LDAP_BIND_SECRET", "darueira-admin123")


def jmap_call(method_calls):
    auth_header = base64.b64encode(f"{STALWART_ADMIN_USER}:{STALWART_ADMIN_PASS}".encode()).decode()
    payload = {
        "using": [
            "urn:ietf:params:jmap:core",
            "urn:stalwart:jmap"
        ],
        "methodCalls": method_calls
    }
    req = urllib.request.Request(
        STALWART_JMAP_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth_header}"
        }
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res.get("methodResponses", [])


def get_objects(object_name):
    res = jmap_call([[f"{object_name}/get", {"ids": None}, "c1"]])
    if res and res[0][0] == f"{object_name}/get":
        return res[0][1].get("list", [])
    return []


def bootstrap_domains():
    print("--> Configuring Mail Domains (darueira.local, globex.local)...")
    existing = {d.get("name"): d.get("id") for d in get_objects("x:Domain")}
    domains_to_ensure = {
        "darueira.local": "Darueira Corporation Primary Domain",
        "globex.local": "Globex Partner Domain"
    }

    create_ops = {}
    for dom_name, desc in domains_to_ensure.items():
        if dom_name not in existing:
            create_ops[f"dom_{dom_name}"] = {
                "name": dom_name,
                "description": desc
            }

    if create_ops:
        res = jmap_call([[
            "x:Domain/set",
            {"create": create_ops},
            "c_dom"
        ]])
        print(f"    Created domains: {list(create_ops.keys())}")
    else:
        print("    All mail domains already exist.")


def bootstrap_system_settings():
    print("--> Configuring System Settings & Default Domain...")
    domains = {d.get("name"): d.get("id") for d in get_objects("x:Domain")}
    darueira_dom_id = domains.get("darueira.local")

    sys_list = get_objects("x:SystemSettings")
    if not sys_list:
        jmap_call([[
            "x:SystemSettings/set",
            {
                "create": {
                    "sys": {
                        "defaultDomainId": darueira_dom_id,
                        "defaultHostname": "stalwart-mail.drr-corpshared-plat.svc.cluster.local"
                    }
                }
            },
            "c_sys"
        ]])
        print(f"    Created SystemSettings with defaultDomainId={darueira_dom_id}")
    else:
        jmap_call([[
            "x:SystemSettings/set",
            {
                "update": {
                    "singleton": {
                        "defaultDomainId": darueira_dom_id,
                        "defaultHostname": "stalwart-mail.drr-corpshared-plat.svc.cluster.local"
                    }
                }
            },
            "c_sys"
        ]])
        print(f"    Updated SystemSettings (defaultDomainId={darueira_dom_id})")


def bootstrap_tracer():
    print("--> Configuring Console Tracing...")
    tracers = get_objects("x:Tracer")
    has_stdout = any(t.get("@type") == "Stdout" for t in tracers)
    if not has_stdout:
        jmap_call([[
            "x:Tracer/set",
            {
                "create": {
                    "console": {
                        "@type": "Stdout",
                        "level": "info",
                        "enable": True,
                        "ansi": False,
                        "buffered": False,
                        "events": {},
                        "eventsPolicy": "exclude"
                    }
                }
            },
            "c_tracer"
        ]])
        print("    Configured Stdout Console Tracer.")
    else:
        print("    Stdout Console Tracer already present.")


def bootstrap_directories_and_auth():
    print("--> Configuring Directory Backends (Authentik LDAP & Keycloak OIDC)...")
    directories = get_objects("x:Directory")
    ldap_dir_id = None
    oidc_dir_id = None

    for d in directories:
        if d.get("@type") == "Ldap":
            ldap_dir_id = d.get("id")
        elif d.get("@type") == "Oidc":
            oidc_dir_id = d.get("id")

    # 1. LDAP Directory
    if not ldap_dir_id:
        res = jmap_call([[
            "x:Directory/set",
            {
                "create": {
                    "authentik-ldap": {
                        "@type": "Ldap",
                        "description": "Authentik Corporate LDAP Directory",
                        "url": LDAP_URL,
                        "baseDn": LDAP_BASE_DN,
                        "bindDn": LDAP_BIND_DN,
                        "bindSecret": {
                            "@type": "Value",
                            "secret": LDAP_BIND_SECRET
                        },
                        "bindAuthentication": True,
                        "filterLogin": "(|(mail=?)(cn=?)(sAMAccountName=?))",
                        "filterMailbox": "(|(mail=?)(cn=?)(sAMAccountName=?))",
                        "useTls": False,
                        "allowInvalidCerts": True,
                        "timeout": 15000
                    }
                }
            },
            "c_ldap"
        ]])
        ldap_dir_id = res[0][1].get("created", {}).get("authentik-ldap", {}).get("id")
        print(f"    Created Authentik LDAP directory (id={ldap_dir_id})")
    else:
        jmap_call([[
            "x:Directory/set",
            {
                "update": {
                    ldap_dir_id: {
                        "description": "Authentik Corporate LDAP Directory",
                        "url": LDAP_URL,
                        "baseDn": LDAP_BASE_DN,
                        "bindDn": LDAP_BIND_DN,
                        "bindSecret": {
                            "@type": "Value",
                            "secret": LDAP_BIND_SECRET
                        },
                        "bindAuthentication": True,
                        "filterLogin": "(|(mail=?)(cn=?)(sAMAccountName=?))",
                        "filterMailbox": "(|(mail=?)(cn=?)(sAMAccountName=?))",
                        "useTls": False,
                        "allowInvalidCerts": True,
                        "timeout": 15000
                    }
                }
            },
            "c_ldap"
        ]])
        print(f"    Updated Authentik LDAP directory (id={ldap_dir_id})")

    # 2. OIDC Directory
    if not oidc_dir_id:
        res = jmap_call([[
            "x:Directory/set",
            {
                "create": {
                    "keycloak-oidc": {
                        "@type": "Oidc",
                        "description": "Keycloak Central IdP OIDC",
                        "issuerUrl": KEYCLOAK_ISSUER_URL,
                        "claimUsername": "email",
                        "usernameDomain": None,
                        "requireAudience": None,
                        "requireScopes": {}
                    }
                }
            },
            "c_oidc"
        ]])
        oidc_dir_id = res[0][1].get("created", {}).get("keycloak-oidc", {}).get("id")
        print(f"    Created Keycloak OIDC directory (id={oidc_dir_id})")
    else:
        jmap_call([[
            "x:Directory/set",
            {
                "update": {
                    oidc_dir_id: {
                        "description": "Keycloak Central IdP OIDC",
                        "issuerUrl": KEYCLOAK_ISSUER_URL,
                        "claimUsername": "email",
                        "usernameDomain": None,
                        "requireAudience": None,
                        "requireScopes": {}
                    }
                }
            },
            "c_oidc"
        ]])
        print(f"    Updated Keycloak OIDC directory (id={oidc_dir_id})")

    # 3. Associate Domains with LDAP Directory
    domains = get_objects("x:Domain")
    for dom in domains:
        dom_id = dom.get("id")
        jmap_call([[
            "x:Domain/set",
            {"update": {dom_id: {"directoryId": ldap_dir_id}}},
            "c_dom_up"
        ]])
    print(f"    Bound domains to LDAP directory (id={ldap_dir_id})")

    # 4. Configure Authentication Singleton
    print("--> Configuring Authentication Singleton & Default Roles...")
    auth_list = get_objects("x:Authentication")
    auth_config = {
        "directoryId": ldap_dir_id,
        "defaultUserRoleIds": {"b": True},
        "defaultGroupRoleIds": {"c": True},
        "defaultAdminRoleIds": {"e": True}
    }
    if not auth_list:
        jmap_call([[
            "x:Authentication/set",
            {"create": {"auth": auth_config}},
            "c_auth"
        ]])
        print(f"    Created Authentication Singleton pointing to LDAP Directory ({ldap_dir_id}).")
    else:
        jmap_call([[
            "x:Authentication/set",
            {"update": {"singleton": auth_config}},
            "c_auth"
        ]])
        print(f"    Updated Authentication Singleton (directoryId={ldap_dir_id}, defaultUserRoleIds=[b]).")


def sync_user_roles():
    print("--> Syncing and Granting Roles to User Accounts...")
    accounts = get_objects("x:Account")
    user_updates = {}
    for acc in accounts:
        if acc.get("@type") == "User":
            user_updates[acc["id"]] = {
                "roles": {
                    "@type": "Custom",
                    "roleIds": {"b": True}
                }
            }
            print(f"    - Granted User Role 'b' to account {acc.get('name')} (id={acc.get('id')})")

    if user_updates:
        jmap_call([[
            "x:Account/set",
            {"update": user_updates},
            "c_sync"
        ]])
        print("    User roles synchronized successfully.")


def main():
    print("==================================================================")
    print("  Bootstrapping Stalwart Mail Server for Darueira Cloud IAM       ")
    print("==================================================================")
    bootstrap_domains()
    bootstrap_system_settings()
    bootstrap_tracer()
    bootstrap_directories_and_auth()
    sync_user_roles()
    print("\n[✓] Stalwart Mail IAM & Federation bootstrap completed successfully!")


if __name__ == "__main__":
    main()
