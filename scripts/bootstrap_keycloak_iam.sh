#!/usr/bin/env bash
# ==============================================================================
# Script: bootstrap_keycloak_iam.sh
# Purpose: Declarative bootstrap of Keycloak Realm, LDAP User Federation,
#          Attribute/Group Mappers, and Generic OIDC/SAML Clients.
# ==============================================================================

set -euo pipefail

NAMESPACE="drr-corpshared-plat"
KEYCLOAK_DEPLOY="deploy/keycloak-server"
REALM_NAME="darueira-platform-svcs"
REALM_DISPLAY="Darueira Platform Services"
LDAP_COMPONENT_NAME="authentik-ldap"
OIDC_CLIENT_ID="darueira-platform-generic-oidc"
OIDC_CLIENT_SECRET="darueira-oidc-secret-key-2026"
SAML_CLIENT_ID="darueira-platform-generic-saml"

log() {
  echo -e "\033[1;34m[IAM-BOOTSTRAP]\033[0m $*"
}

log "Authenticating kcadm.sh inside Keycloak..."
kubectl exec -n "$NAMESPACE" "$KEYCLOAK_DEPLOY" -- /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8080 --realm master --user admin --password admin123-dev

log "Checking if realm '$REALM_NAME' exists..."
if ! kubectl exec -n "$NAMESPACE" "$KEYCLOAK_DEPLOY" -- /opt/keycloak/bin/kcadm.sh get "realms/$REALM_NAME" >/dev/null 2>&1; then
  log "Creating realm '$REALM_NAME'..."
  kubectl exec -n "$NAMESPACE" "$KEYCLOAK_DEPLOY" -- /opt/keycloak/bin/kcadm.sh create realms \
    -s "realm=$REALM_NAME" -s enabled=true -s "displayName=$REALM_DISPLAY" -s accessTokenLifespan=300
else
  log "Realm '$REALM_NAME' already exists."
fi

REALM_ID=$(kubectl exec -n "$NAMESPACE" "$KEYCLOAK_DEPLOY" -- /opt/keycloak/bin/kcadm.sh get "realms/$REALM_NAME" | grep '"id"' | head -n1 | cut -d'"' -f4)
log "Realm '$REALM_NAME' ID: $REALM_ID"

log "Configuring LDAP User Storage Provider ($LDAP_COMPONENT_NAME)..."
EXISTING_LDAP_ID=$(kubectl exec -n "$NAMESPACE" "$KEYCLOAK_DEPLOY" -- /opt/keycloak/bin/kcadm.sh get components -r "$REALM_NAME" | grep -B2 '"authentik-ldap"' | grep '"id"' | cut -d'"' -f4 || true)

if [ -n "$EXISTING_LDAP_ID" ]; then
  log "Updating existing LDAP Provider ID: $EXISTING_LDAP_ID"
  kubectl exec -i -n "$NAMESPACE" "$KEYCLOAK_DEPLOY" -- /opt/keycloak/bin/kcadm.sh update "components/$EXISTING_LDAP_ID" -r "$REALM_NAME" -f - <<EOF
{
  "name": "$LDAP_COMPONENT_NAME",
  "providerId": "ldap",
  "providerType": "org.keycloak.storage.UserStorageProvider",
  "parentId": "$REALM_ID",
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
    "pagination": ["true"],
    "batchSizeForSync": ["1000"],
    "importEnabled": ["true"]
  }
}
EOF
  LDAP_ID="$EXISTING_LDAP_ID"
else
  log "Creating new LDAP Provider..."
  LDAP_ID=$(kubectl exec -i -n "$NAMESPACE" "$KEYCLOAK_DEPLOY" -- /opt/keycloak/bin/kcadm.sh create components -r "$REALM_NAME" -f - <<EOF | grep "Created new component" | cut -d"'" -f2
{
  "name": "$LDAP_COMPONENT_NAME",
  "providerId": "ldap",
  "providerType": "org.keycloak.storage.UserStorageProvider",
  "parentId": "$REALM_ID",
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
    "pagination": ["true"],
    "batchSizeForSync": ["1000"],
    "importEnabled": ["true"]
  }
}
EOF
)
fi

log "Ensuring LDAP Mappers exist on LDAP Provider ($LDAP_ID)..."

create_mapper_if_missing() {
  local mapper_name="$1"
  local json_payload="$2"
  if ! kubectl exec -n "$NAMESPACE" "$KEYCLOAK_DEPLOY" -- /opt/keycloak/bin/kcadm.sh get components -r "$REALM_NAME" | grep -q "\"$mapper_name\""; then
    log "Creating mapper: $mapper_name"
    kubectl exec -i -n "$NAMESPACE" "$KEYCLOAK_DEPLOY" -- /opt/keycloak/bin/kcadm.sh create components -r "$REALM_NAME" -f - <<< "$json_payload"
  else
    log "Mapper '$mapper_name' already exists."
  fi
}

create_mapper_if_missing "department-mapper" "{
  \"name\": \"department-mapper\",
  \"providerId\": \"user-attribute-ldap-mapper\",
  \"providerType\": \"org.keycloak.storage.ldap.mappers.LDAPStorageMapper\",
  \"parentId\": \"$LDAP_ID\",
  \"config\": {
    \"ldap.attribute\": [\"department\"],
    \"is.mandatory.in.ldap\": [\"false\"],
    \"read.only\": [\"true\"],
    \"always.read.value.from.ldap\": [\"true\"],
    \"user.model.attribute\": [\"department\"]
  }
}"

create_mapper_if_missing "tenant-mapper" "{
  \"name\": \"tenant-mapper\",
  \"providerId\": \"user-attribute-ldap-mapper\",
  \"providerType\": \"org.keycloak.storage.ldap.mappers.LDAPStorageMapper\",
  \"parentId\": \"$LDAP_ID\",
  \"config\": {
    \"ldap.attribute\": [\"department\"],
    \"is.mandatory.in.ldap\": [\"false\"],
    \"read.only\": [\"true\"],
    \"always.read.value.from.ldap\": [\"true\"],
    \"user.model.attribute\": [\"tenant\"]
  }
}"

create_mapper_if_missing "position-mapper" "{
  \"name\": \"position-mapper\",
  \"providerId\": \"user-attribute-ldap-mapper\",
  \"providerType\": \"org.keycloak.storage.ldap.mappers.LDAPStorageMapper\",
  \"parentId\": \"$LDAP_ID\",
  \"config\": {
    \"ldap.attribute\": [\"position\"],
    \"is.mandatory.in.ldap\": [\"false\"],
    \"read.only\": [\"true\"],
    \"always.read.value.from.ldap\": [\"true\"],
    \"user.model.attribute\": [\"position\"]
  }
}"

create_mapper_if_missing "employee-type-mapper" "{
  \"name\": \"employee-type-mapper\",
  \"providerId\": \"user-attribute-ldap-mapper\",
  \"providerType\": \"org.keycloak.storage.ldap.mappers.LDAPStorageMapper\",
  \"parentId\": \"$LDAP_ID\",
  \"config\": {
    \"ldap.attribute\": [\"employee_type\"],
    \"is.mandatory.in.ldap\": [\"false\"],
    \"read.only\": [\"true\"],
    \"always.read.value.from.ldap\": [\"true\"],
    \"user.model.attribute\": [\"employee_type\"]
  }
}"

create_mapper_if_missing "groups-mapper" "{
  \"name\": \"groups-mapper\",
  \"providerId\": \"group-ldap-mapper\",
  \"providerType\": \"org.keycloak.storage.ldap.mappers.LDAPStorageMapper\",
  \"parentId\": \"$LDAP_ID\",
  \"config\": {
    \"groups.dn\": [\"ou=groups,dc=darueira,dc=local\"],
    \"group.name.ldap.attribute\": [\"cn\"],
    \"group.object.classes\": [\"groupOfNames, posixGroup\"],
    \"preserve.group.inheritance\": [\"false\"],
    \"ignore.missing.groups\": [\"false\"],
    \"membership.ldap.attribute\": [\"member\"],
    \"membership.attribute.type\": [\"DN\"],
    \"membership.user.ldap.attribute\": [\"cn\"],
    \"mode\": [\"READ_ONLY\"],
    \"user.roles.retrieve.strategy\": [\"LOAD_GROUPS_BY_MEMBER_ATTRIBUTE\"]
  }
}"

log "Triggering full sync for users and groups..."
kubectl exec -n "$NAMESPACE" "$KEYCLOAK_DEPLOY" -- /opt/keycloak/bin/kcadm.sh create "user-storage/$LDAP_ID/sync" -r "$REALM_NAME" -q action=triggerFullSync || true

GROUPS_MAPPER_ID=$(kubectl exec -n "$NAMESPACE" "$KEYCLOAK_DEPLOY" -- /opt/keycloak/bin/kcadm.sh get components -r "$REALM_NAME" | grep -B2 '"groups-mapper"' | grep '"id"' | cut -d'"' -f4 || true)
if [ -n "$GROUPS_MAPPER_ID" ]; then
  kubectl exec -n "$NAMESPACE" "$KEYCLOAK_DEPLOY" -- /opt/keycloak/bin/kcadm.sh create "user-storage/$LDAP_ID/mappers/$GROUPS_MAPPER_ID/sync" -r "$REALM_NAME" -q direction=fedToKeycloak || true
fi

log "Configuring Generic OIDC Client ($OIDC_CLIENT_ID)..."
if ! kubectl exec -n "$NAMESPACE" "$KEYCLOAK_DEPLOY" -- /opt/keycloak/bin/kcadm.sh get clients -r "$REALM_NAME" | grep -q "\"$OIDC_CLIENT_ID\""; then
  kubectl exec -i -n "$NAMESPACE" "$KEYCLOAK_DEPLOY" -- /opt/keycloak/bin/kcadm.sh create clients -r "$REALM_NAME" -f - <<EOF
{
  "clientId": "$OIDC_CLIENT_ID",
  "name": "Darueira Platform Generic OIDC Client",
  "description": "Generic confidential OIDC client for platform microservices and applications",
  "protocol": "openid-connect",
  "enabled": true,
  "publicClient": false,
  "clientAuthenticatorType": "client-secret",
  "secret": "$OIDC_CLIENT_SECRET",
  "standardFlowEnabled": true,
  "directAccessGrantsEnabled": true,
  "serviceAccountsEnabled": true,
  "fullScopeAllowed": true,
  "redirectUris": ["*"],
  "webOrigins": ["*"],
  "protocolMappers": [
    {
      "name": "tenant-claim",
      "protocol": "openid-connect",
      "protocolMapper": "oidc-usermodel-attribute-mapper",
      "consentRequired": false,
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
      "consentRequired": false,
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
      "consentRequired": false,
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
      "consentRequired": false,
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
      "consentRequired": false,
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
EOF
else
  log "OIDC Client '$OIDC_CLIENT_ID' already exists."
fi

log "Configuring Generic SAML Client ($SAML_CLIENT_ID)..."
if ! kubectl exec -n "$NAMESPACE" "$KEYCLOAK_DEPLOY" -- /opt/keycloak/bin/kcadm.sh get clients -r "$REALM_NAME" | grep -q "\"$SAML_CLIENT_ID\""; then
  kubectl exec -i -n "$NAMESPACE" "$KEYCLOAK_DEPLOY" -- /opt/keycloak/bin/kcadm.sh create clients -r "$REALM_NAME" -f - <<EOF
{
  "clientId": "$SAML_CLIENT_ID",
  "name": "Darueira Platform Generic SAML Client",
  "description": "Generic SAML 2.0 client for platform services",
  "protocol": "saml",
  "enabled": true,
  "publicClient": false,
  "standardFlowEnabled": true,
  "directAccessGrantsEnabled": false,
  "baseUrl": "http://localhost",
  "redirectUris": ["*"],
  "attributes": {
    "saml.authnstatement": "true",
    "saml.server.signature": "false",
    "saml.client.signature": "false",
    "saml_name_id_format": "username",
    "saml.force.post.binding": "true"
  },
  "protocolMappers": [
    {
      "name": "X500 email",
      "protocol": "saml",
      "protocolMapper": "saml-user-property-mapper",
      "consentRequired": false,
      "config": {
        "user.attribute": "email",
        "attribute.name": "urn:oid:1.2.840.113549.1.9.1",
        "attribute.nameformat": "urn:oasis:names:tc:SAML:2.0:attrname-format:uri",
        "friendly.name": "email"
      }
    },
    {
      "name": "tenant-attribute",
      "protocol": "saml",
      "protocolMapper": "saml-user-attribute-mapper",
      "consentRequired": false,
      "config": {
        "user.attribute": "tenant",
        "attribute.name": "tenant",
        "attribute.nameformat": "urn:oasis:names:tc:SAML:2.0:attrname-format:basic",
        "friendly.name": "tenant"
      }
    },
    {
      "name": "role-list",
      "protocol": "saml",
      "protocolMapper": "saml-role-list-mapper",
      "consentRequired": false,
      "config": {
        "attribute.name": "Role",
        "attribute.nameformat": "urn:oasis:names:tc:SAML:2.0:attrname-format:basic",
        "single": "false"
      }
    }
  ]
}
EOF
else
  log "SAML Client '$SAML_CLIENT_ID' already exists."
fi

log "Keycloak IAM Bootstrap Completed Successfully!"
