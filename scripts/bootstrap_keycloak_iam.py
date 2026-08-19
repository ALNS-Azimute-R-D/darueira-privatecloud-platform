#!/usr/bin/env python3
"""
==============================================================================
Script: scripts/bootstrap_keycloak_iam.py
Purpose: Declarative, idempotent bootstrap of Keycloak Realm, LDAP User
         Federation (Authentik Outpost), Attribute/Group Mappers, and
         OIDC Clients (Generic Confidential & Stalwart Public WebUI).
==============================================================================
"""

import json
import os
import sys
import urllib.request
import urllib.parse

KEYCLOAK_BASE_URL = os.environ.get("KEYCLOAK_BASE_URL", "http://keycloak.drr-corpshared-plat.svc.cluster.local:8080")
KEYCLOAK_ADMIN_USER = os.environ.get("KEYCLOAK_ADMIN_USER", "admin")
KEYCLOAK_ADMIN_PASS = os.environ.get("KEYCLOAK_ADMIN_PASS", "admin123-dev")

REALM_NAME = "darueira-platform-svcs"
REALM_DISPLAY = "Darueira Platform Services"
FRONTEND_URL = "https://keycloak.darueira-corpshared.127.0.0.1.nip.io"
LDAP_COMPONENT_NAME = "authentik-ldap"

OIDC_GENERIC_CLIENT_ID = "darueira-platform-generic-oidc"
OIDC_GENERIC_CLIENT_SECRET = "darueira-oidc-secret-key-2026"
SAML_GENERIC_CLIENT_ID = "darueira-platform-generic-saml"
STALWART_WEBUI_CLIENT_ID = "stalwart-webui"


class KeycloakAdminClient:
    def __init__(self, base_url, user, password):
        self.base_url = base_url.rstrip("/")
        self.token = self._get_token(user, password)

    def _get_token(self, user, password):
        url = f"{self.base_url}/realms/master/protocol/openid-connect/token"
        data = urllib.parse.urlencode({
            "client_id": "admin-cli",
            "username": user,
            "password": password,
            "grant_type": "password"
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))["access_token"]

    def request(self, path, method="GET", data=None):
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        body = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                status = resp.status
                if status == 204 or resp.length == 0:
                    return None
                content = resp.read()
                return json.loads(content.decode("utf-8")) if content else None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            err_body = e.read().decode("utf-8") if e.fp else ""
            print(f"[ERROR] HTTP {e.code} on {method} {url}: {err_body}", file=sys.stderr)
            raise


def bootstrap():
    print("==================================================================")
    print("  Bootstrapping Keycloak Central IdP Realm & IAM Federation       ")
    print("==================================================================")

    kc = KeycloakAdminClient(KEYCLOAK_BASE_URL, KEYCLOAK_ADMIN_USER, KEYCLOAK_ADMIN_PASS)

    # 1. Realm
    print(f"--> Ensuring Realm '{REALM_NAME}' exists...")
    realm = kc.request(f"admin/realms/{REALM_NAME}")
    if not realm:
        print(f"    Creating Realm '{REALM_NAME}'...")
        kc.request("admin/realms", method="POST", data={
            "realm": REALM_NAME,
            "displayName": REALM_DISPLAY,
            "enabled": True,
            "accessTokenLifespan": 300,
            "attributes": {
                "frontendUrl": FRONTEND_URL
            }
        })
        realm = kc.request(f"admin/realms/{REALM_NAME}")
    else:
        print(f"    Updating Realm '{REALM_NAME}' frontendUrl to {FRONTEND_URL}...")
        realm["displayName"] = REALM_DISPLAY
        realm["bruteForceProtected"] = False
        if "attributes" not in realm or realm["attributes"] is None:
            realm["attributes"] = {}
        realm["attributes"]["frontendUrl"] = FRONTEND_URL
        kc.request(f"admin/realms/{REALM_NAME}", method="PUT", data=realm)

    realm_id = realm["id"]
    print(f"    Realm '{REALM_NAME}' ready (ID: {realm_id}).")

    # 2. LDAP Provider
    print(f"--> Configuring LDAP User Federation ({LDAP_COMPONENT_NAME})...")
    components = kc.request(f"admin/realms/{REALM_NAME}/components?type=org.keycloak.storage.UserStorageProvider") or []
    ldap_comp = next((c for c in components if c.get("name") == LDAP_COMPONENT_NAME), None)

    ldap_config = {
        "name": LDAP_COMPONENT_NAME,
        "providerId": "ldap",
        "providerType": "org.keycloak.storage.UserStorageProvider",
        "parentId": realm_id,
        "config": {
            "enabled": ["true"],
            "priority": ["0"],
            "fullSyncPeriod": ["-1"],
            "changedSyncPeriod": ["-1"],
            "editMode": ["READ_ONLY"],
            "syncRegistrations": ["false"],
            "vendor": ["other"],
            "usernameLDAPAttribute": ["cn"],
            "rdnLDAPAttribute": ["cn"],
            "uuidLDAPAttribute": ["uid"],
            "userObjectClasses": ["inetOrgPerson, organizationalPerson, person"],
            "connectionUrl": ["ldap://authentik-ldap-outpost.drr-corpshared-plat.svc.cluster.local:389"],
            "usersDn": ["ou=users,dc=darueira,dc=local"],
            "authType": ["simple"],
            "bindDn": ["cn=akadmin,ou=users,dc=darueira,dc=local"],
            "bindCredential": ["darueira-admin123"],
            "searchScope": ["1"],
            "validatePasswordPolicy": ["false"],
            "trustEmail": ["true"],
            "useTruststoreSpi": ["always"],
            "connectionPooling": ["true"],
            "connectionTimeout": ["15000"],
            "readTimeout": ["15000"],
            "cachePolicy": ["DEFAULT"],
            "pagination": ["true"],
            "batchSizeForSync": ["1000"],
            "importEnabled": ["true"]
        }
    }

    if not ldap_comp:
        kc.request(f"admin/realms/{REALM_NAME}/components", method="POST", data=ldap_config)
        components = kc.request(f"admin/realms/{REALM_NAME}/components?type=org.keycloak.storage.UserStorageProvider") or []
        ldap_comp = next((c for c in components if c.get("name") == LDAP_COMPONENT_NAME), None)
        print(f"    Created LDAP Provider (ID: {ldap_comp['id']})")
    else:
        ldap_config["id"] = ldap_comp["id"]
        kc.request(f"admin/realms/{REALM_NAME}/components/{ldap_comp['id']}", method="PUT", data=ldap_config)
        print(f"    Updated LDAP Provider (ID: {ldap_comp['id']})")

    ldap_id = ldap_comp["id"]

    # 3. LDAP Mappers
    print("--> Configuring LDAP Mappers...")
    existing_mappers = kc.request(f"admin/realms/{REALM_NAME}/components?parent={ldap_id}&type=org.keycloak.storage.ldap.mappers.LDAPStorageMapper") or []
    
    # Deduplicate existing mappers if duplicates exist
    seen_names = {}
    for m in existing_mappers:
        name = m.get("name")
        if name in seen_names:
            print(f"    Deleting duplicate mapper '{name}' (ID: {m['id']})...")
            kc.request(f"admin/realms/{REALM_NAME}/components/{m['id']}", method="DELETE")
        else:
            seen_names[name] = m

    # Re-fetch cleaned mappers
    existing_mappers = kc.request(f"admin/realms/{REALM_NAME}/components?parent={ldap_id}&type=org.keycloak.storage.ldap.mappers.LDAPStorageMapper") or []
    mapper_map = {m.get("name"): m for m in existing_mappers}

    mappers_to_ensure = [
        {
            "name": "department-mapper",
            "providerId": "user-attribute-ldap-mapper",
            "providerType": "org.keycloak.storage.ldap.mappers.LDAPStorageMapper",
            "parentId": ldap_id,
            "config": {
                "ldap.attribute": ["department"],
                "is.mandatory.in.ldap": ["false"],
                "read.only": ["true"],
                "always.read.value.from.ldap": ["true"],
                "user.model.attribute": ["department"]
            }
        },
        {
            "name": "tenant-mapper",
            "providerId": "user-attribute-ldap-mapper",
            "providerType": "org.keycloak.storage.ldap.mappers.LDAPStorageMapper",
            "parentId": ldap_id,
            "config": {
                "ldap.attribute": ["department"],
                "is.mandatory.in.ldap": ["false"],
                "read.only": ["true"],
                "always.read.value.from.ldap": ["true"],
                "user.model.attribute": ["tenant"]
            }
        },
        {
            "name": "position-mapper",
            "providerId": "user-attribute-ldap-mapper",
            "providerType": "org.keycloak.storage.ldap.mappers.LDAPStorageMapper",
            "parentId": ldap_id,
            "config": {
                "ldap.attribute": ["position"],
                "is.mandatory.in.ldap": ["false"],
                "read.only": ["true"],
                "always.read.value.from.ldap": ["true"],
                "user.model.attribute": ["position"]
            }
        },
        {
            "name": "employee-type-mapper",
            "providerId": "user-attribute-ldap-mapper",
            "providerType": "org.keycloak.storage.ldap.mappers.LDAPStorageMapper",
            "parentId": ldap_id,
            "config": {
                "ldap.attribute": ["employee_type"],
                "is.mandatory.in.ldap": ["false"],
                "read.only": ["true"],
                "always.read.value.from.ldap": ["true"],
                "user.model.attribute": ["employee_type"]
            }
        },
        {
            "name": "groups-mapper",
            "providerId": "group-ldap-mapper",
            "providerType": "org.keycloak.storage.ldap.mappers.LDAPStorageMapper",
            "parentId": ldap_id,
            "config": {
                "groups.dn": ["ou=groups,dc=darueira,dc=local"],
                "group.name.ldap.attribute": ["cn"],
                "group.object.classes": ["groupOfNames, posixGroup"],
                "preserve.group.inheritance": ["false"],
                "ignore.missing.groups": ["false"],
                "membership.ldap.attribute": ["member"],
                "membership.attribute.type": ["DN"],
                "membership.user.ldap.attribute": ["cn"],
                "mode": ["READ_ONLY"],
                "user.roles.retrieve.strategy": ["LOAD_GROUPS_BY_MEMBER_ATTRIBUTE"]
            }
        }
    ]

    for mapper in mappers_to_ensure:
        m_name = mapper["name"]
        if m_name not in mapper_map:
            kc.request(f"admin/realms/{REALM_NAME}/components", method="POST", data=mapper)
            print(f"    Created mapper: {m_name}")
        else:
            mapper["id"] = mapper_map[m_name]["id"]
            kc.request(f"admin/realms/{REALM_NAME}/components/{mapper['id']}", method="PUT", data=mapper)
            print(f"    Updated mapper: {m_name}")

    # 4. Trigger LDAP Full Sync
    print("--> Triggering LDAP full sync for users and groups...")
    try:
        kc.request(f"admin/realms/{REALM_NAME}/user-storage/{ldap_id}/sync?action=triggerFullSync", method="POST")
        print("    Full user sync triggered.")
    except Exception as e:
        print(f"    User sync warning: {e}")

    # 5. Generic Confidential OIDC Client
    print(f"--> Configuring Generic Confidential OIDC Client ({OIDC_GENERIC_CLIENT_ID})...")
    clients = kc.request(f"admin/realms/{REALM_NAME}/clients?clientId={OIDC_GENERIC_CLIENT_ID}") or []
    generic_client_payload = {
        "clientId": OIDC_GENERIC_CLIENT_ID,
        "name": "Darueira Platform Generic OIDC Client",
        "description": "Generic confidential OIDC client for platform microservices and applications",
        "protocol": "openid-connect",
        "enabled": True,
        "publicClient": False,
        "clientAuthenticatorType": "client-secret",
        "secret": OIDC_GENERIC_CLIENT_SECRET,
        "standardFlowEnabled": True,
        "directAccessGrantsEnabled": True,
        "serviceAccountsEnabled": True,
        "fullScopeAllowed": True,
        "redirectUris": ["*"],
        "webOrigins": ["*"],
        "protocolMappers": [
            {
                "name": "tenant-claim",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-attribute-mapper",
                "consentRequired": False,
                "config": {
                    "user.attribute": "tenant",
                    "claim.name": "tenant",
                    "jsonType.label": "String",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true"
                }
            },
            {
                "name": "department-claim",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-attribute-mapper",
                "consentRequired": False,
                "config": {
                    "user.attribute": "department",
                    "claim.name": "department",
                    "jsonType.label": "String",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true"
                }
            },
            {
                "name": "position-claim",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-attribute-mapper",
                "consentRequired": False,
                "config": {
                    "user.attribute": "position",
                    "claim.name": "position",
                    "jsonType.label": "String",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true"
                }
            },
            {
                "name": "employee-type-claim",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-attribute-mapper",
                "consentRequired": False,
                "config": {
                    "user.attribute": "employee_type",
                    "claim.name": "employee_type",
                    "jsonType.label": "String",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true"
                }
            },
            {
                "name": "groups-claim",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-group-membership-mapper",
                "consentRequired": False,
                "config": {
                    "claim.name": "groups",
                    "full.path": "false",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true"
                }
            },
            {
                "name": "minio-policy-claim",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-hardcoded-claim-mapper",
                "consentRequired": False,
                "config": {
                    "claim.name": "policy",
                    "claim.value": "consoleAdmin",
                    "jsonType.label": "String",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true"
                }
            }
        ]
    }
    if not clients:
        kc.request(f"admin/realms/{REALM_NAME}/clients", method="POST", data=generic_client_payload)
        print(f"    Created client '{OIDC_GENERIC_CLIENT_ID}'.")
    else:
        c_id = clients[0]["id"]
        generic_client_payload["id"] = c_id
        kc.request(f"admin/realms/{REALM_NAME}/clients/{c_id}", method="PUT", data=generic_client_payload)
        print(f"    Updated client '{OIDC_GENERIC_CLIENT_ID}'.")

    # 6. Stalwart Public WebUI Client
    print(f"--> Configuring Stalwart Public WebUI Client ({STALWART_WEBUI_CLIENT_ID})...")
    st_clients = kc.request(f"admin/realms/{REALM_NAME}/clients?clientId={STALWART_WEBUI_CLIENT_ID}") or []
    st_payload = {
        "clientId": STALWART_WEBUI_CLIENT_ID,
        "name": "Stalwart Mail WebUI & Administration",
        "description": "Public OIDC Client for Stalwart Mail Server Web Interface and WebMail",
        "protocol": "openid-connect",
        "enabled": True,
        "publicClient": True,
        "standardFlowEnabled": True,
        "implicitFlowEnabled": False,
        "directAccessGrantsEnabled": True,
        "serviceAccountsEnabled": False,
        "fullScopeAllowed": True,
        "redirectUris": [
            "https://mail.darueira-corpshared.127.0.0.1.nip.io/*",
            "https://mail.darueira-corpshared.127.0.0.1.nip.io:9443/*",
            "http://mail.darueira-corpshared.127.0.0.1.nip.io:9080/*",
            "https://mail.darueira-corpshared.local/*",
            "https://stalwart.darueira-corpshared.127.0.0.1.nip.io/*",
            "https://stalwart.darueira-corpshared.127.0.0.1.nip.io:9443/*",
            "https://stalwart.darueira-corpshared.local/*",
            "https://*.darueira-corpshared.127.0.0.1.nip.io/*",
            "https://*.darueira-corpshared.127.0.0.1.nip.io:9443/*",
            "http://*.darueira-corpshared.127.0.0.1.nip.io:9080/*",
            "http://localhost:*/*",
            "*"
        ],
        "webOrigins": ["*"],
        "attributes": {
            "pkce.code.challenge.method": "S256",
            "post.logout.redirect.uris": "+"
        },
        "protocolMappers": [
            {
                "name": "tenant-claim",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-attribute-mapper",
                "consentRequired": False,
                "config": {
                    "user.attribute": "tenant",
                    "claim.name": "tenant",
                    "jsonType.label": "String",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true"
                }
            },
            {
                "name": "groups-claim",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-group-membership-mapper",
                "consentRequired": False,
                "config": {
                    "claim.name": "groups",
                    "full.path": "false",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true"
                }
            }
        ]
    }
    if not st_clients:
        kc.request(f"admin/realms/{REALM_NAME}/clients", method="POST", data=st_payload)
        print(f"    Created client '{STALWART_WEBUI_CLIENT_ID}'.")
    else:
        st_id = st_clients[0]["id"]
        st_payload["id"] = st_id
        kc.request(f"admin/realms/{REALM_NAME}/clients/{st_id}", method="PUT", data=st_payload)
        print(f"    Updated client '{STALWART_WEBUI_CLIENT_ID}'.")

    # 7. Forgejo Git OIDC Client
    FORGEJO_CLIENT_ID = "forgejo-git"
    FORGEJO_CLIENT_SECRET = "darueira-forgejo-secret-2026"
    print(f"--> Configuring Forgejo Git OIDC Client ({FORGEJO_CLIENT_ID})...")
    fj_clients = kc.request(f"admin/realms/{REALM_NAME}/clients?clientId={FORGEJO_CLIENT_ID}") or []
    fj_payload = {
        "clientId": FORGEJO_CLIENT_ID,
        "name": "Forgejo Git Server",
        "description": "Internal Git Repository Manager with Keycloak OIDC Authentication",
        "protocol": "openid-connect",
        "enabled": True,
        "publicClient": False,
        "clientAuthenticatorType": "client-secret",
        "secret": FORGEJO_CLIENT_SECRET,
        "standardFlowEnabled": True,
        "directAccessGrantsEnabled": True,
        "serviceAccountsEnabled": True,
        "fullScopeAllowed": True,
        "redirectUris": [
            "https://git.darueira-corpshared.127.0.0.1.nip.io/*",
            "https://git.darueira-corpshared.127.0.0.1.nip.io:9443/*",
            "http://git.darueira-corpshared.127.0.0.1.nip.io:9080/*",
            "https://git.darueira-corpshared.127.0.0.1.nip.io/user/oauth2/keycloak-oidc/callback",
            "https://git.darueira-corpshared.127.0.0.1.nip.io:9443/user/oauth2/keycloak-oidc/callback",
            "http://git.darueira-corpshared.127.0.0.1.nip.io:9080/user/oauth2/keycloak-oidc/callback",
            "http://localhost:*/*",
            "*"
        ],
        "webOrigins": ["*"],
        "protocolMappers": [
            {
                "name": "email-claim",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-attribute-mapper",
                "consentRequired": False,
                "config": {
                    "user.attribute": "email",
                    "claim.name": "email",
                    "jsonType.label": "String",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true"
                }
            },
            {
                "name": "groups-claim",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-group-membership-mapper",
                "consentRequired": False,
                "config": {
                    "claim.name": "groups",
                    "full.path": "false",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true"
                }
            },
            {
                "name": "tenant-claim",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-attribute-mapper",
                "consentRequired": False,
                "config": {
                    "user.attribute": "tenant",
                    "claim.name": "tenant",
                    "jsonType.label": "String",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true"
                }
            }
        ]
    }
    if not fj_clients:
        kc.request(f"admin/realms/{REALM_NAME}/clients", method="POST", data=fj_payload)
        print(f"    Created client '{FORGEJO_CLIENT_ID}'.")
    else:
        fj_id = fj_clients[0]["id"]
        fj_payload["id"] = fj_id
        kc.request(f"admin/realms/{REALM_NAME}/clients/{fj_id}", method="PUT", data=fj_payload)
        print(f"    Updated client '{FORGEJO_CLIENT_ID}'.")

    # 8. ArgoCD GitOps OIDC Client
    ARGOCD_CLIENT_ID = "argocd"
    ARGOCD_CLIENT_SECRET = "darueira-argocd-secret-2026"
    print(f"--> Configuring ArgoCD GitOps OIDC Client ({ARGOCD_CLIENT_ID})...")
    argo_clients = kc.request(f"admin/realms/{REALM_NAME}/clients?clientId={ARGOCD_CLIENT_ID}") or []
    argo_payload = {
        "clientId": ARGOCD_CLIENT_ID,
        "name": "ArgoCD Continuous Delivery",
        "description": "GitOps Continuous Delivery Platform with Keycloak OIDC Authentication",
        "protocol": "openid-connect",
        "enabled": True,
        "publicClient": False,
        "clientAuthenticatorType": "client-secret",
        "secret": ARGOCD_CLIENT_SECRET,
        "standardFlowEnabled": True,
        "directAccessGrantsEnabled": True,
        "serviceAccountsEnabled": True,
        "fullScopeAllowed": True,
        "redirectUris": [
            "https://argocd.darueira-corpshared.127.0.0.1.nip.io/auth/callback",
            "https://argocd.darueira-corpshared.127.0.0.1.nip.io:9443/auth/callback",
            "http://argocd.darueira-corpshared.127.0.0.1.nip.io:9080/auth/callback",
            "https://argocd.darueira-corpshared.local/auth/callback",
            "http://localhost:*/*",
            "*"
        ],
        "webOrigins": ["*"],
        "protocolMappers": [
            {
                "name": "groups-claim",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-group-membership-mapper",
                "consentRequired": False,
                "config": {
                    "claim.name": "groups",
                    "full.path": "false",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true"
                }
            },
            {
                "name": "email-claim",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-attribute-mapper",
                "consentRequired": False,
                "config": {
                    "user.attribute": "email",
                    "claim.name": "email",
                    "jsonType.label": "String",
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                    "userinfo.token.claim": "true"
                }
            }
        ]
    }
    if not argo_clients:
        kc.request(f"admin/realms/{REALM_NAME}/clients", method="POST", data=argo_payload)
        print(f"    Created client '{ARGOCD_CLIENT_ID}'.")
    else:
        argo_id = argo_clients[0]["id"]
        argo_payload["id"] = argo_id
        kc.request(f"admin/realms/{REALM_NAME}/clients/{argo_id}", method="PUT", data=argo_payload)
        print(f"    Updated client '{ARGOCD_CLIENT_ID}'.")

    print("\n[✓] Keycloak Central IAM Federation bootstrap completed successfully!")


if __name__ == "__main__":
    bootstrap()
