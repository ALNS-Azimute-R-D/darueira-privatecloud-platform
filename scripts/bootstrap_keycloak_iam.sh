#!/usr/bin/env bash
# ==============================================================================
# Script: bootstrap_keycloak_iam.sh
# Purpose: Wrapper to execute Keycloak declarative IAM bootstrap
# ==============================================================================

set -euo pipefail

NAMESPACE="drr-corpshared-plat"
AUTHENTIK_SERVER="deploy/authentik-server"

echo -e "\033[1;34m[IAM-BOOTSTRAP]\033[0m Running Keycloak declarative bootstrap..."
kubectl exec -i -n "$NAMESPACE" "$AUTHENTIK_SERVER" -c server -- python3 < scripts/bootstrap_keycloak_iam.py
