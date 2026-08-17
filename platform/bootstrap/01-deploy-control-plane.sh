#!/usr/bin/env bash
# ==============================================================================
# Script: 01-deploy-control-plane.sh
# Project: darueira-privatecloud-platform
# Description: Initializes enterprise shared namespaces and applies base
#              control plane services (Authentik, Central DB, MinIO, Vault, Backstage).
# ==============================================================================

set -euo pipefail

# ANSI Color Codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

log_banner() {
    echo -e "${CYAN}================================================================${NC}"
    echo -e "${CYAN}  Darueira Private Cloud - Control Plane Bootstrap              ${NC}"
    echo -e "${CYAN}================================================================${NC}"
}

log_banner

# Determine Kubernetes CLI tool (prefer kubectl, fallback to microk8s kubectl)
if command -v kubectl &>/dev/null; then
    KUBECTL="kubectl"
elif command -v microk8s &>/dev/null; then
    KUBECTL="microk8s kubectl"
else
    log_error "Neither 'kubectl' nor 'microk8s' command found in PATH."
    exit 1
fi

log_info "Using Kubernetes CLI: ${KUBECTL}"

# Locate Repository Root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

log_info "Platform repository root: ${REPO_ROOT}"

# 1. Initialize Namespaces
NAMESPACES=(
    "drr-corpshared-secr-internal"
    "drr-corpshared-plat"
    "drr-corpshared-obs"
    "drr-corpshared-mgmt"
)

log_info "Creating and validating core Enterprise Shared Services namespaces..."
for ns in "${NAMESPACES[@]}"; do
    if ! ${KUBECTL} get namespace "${ns}" &>/dev/null; then
        log_info "Creating namespace: ${ns}..."
        ${KUBECTL} create namespace "${ns}"
        ${KUBECTL} label namespace "${ns}" \
            darueira.io/tier=enterprise-shared \
            pod-security.kubernetes.io/enforce=restricted \
            pod-security.kubernetes.io/audit=restricted \
            pod-security.kubernetes.io/warn=restricted \
            --overwrite
    else
        log_success "Namespace already exists: ${ns}"
    fi
done

# 2. Deploy CRDs, StorageClass and PersistentVolumes
log_info "Applying Darueira CRDs..."
${KUBECTL} apply -f "${REPO_ROOT}/operators/darueira-operator/config/crd/bases/"

log_info "Applying Darueira Host StorageClass & PersistentVolumes..."
${KUBECTL} apply -f "${REPO_ROOT}/platform/kustomize/base/storage-class.yaml"
${KUBECTL} apply -f "${REPO_ROOT}/platform/kustomize/base/storage-pvs.yaml"

# 3. Deploy Security & Secrets Internal Base (OpenBao / SPIRE / cert-manager)
log_info "Applying Base Kustomize: corpshared-secr-internal..."
${KUBECTL} apply -k "${REPO_ROOT}/platform/kustomize/base/corpshared-secr-internal"

# 3. Deploy Platform Persistence, Identity & Messaging (Postgres 17, MinIO, Nexus, Stalwart, Keycloak, Kafka)
log_info "Applying Base Kustomize: corpshared-plat..."
${KUBECTL} apply -k "${REPO_ROOT}/platform/kustomize/base/corpshared-plat"

# 4. Deploy Observability Tier (Prometheus, Grafana, OpenSearch, Jaeger, OpenTelemetry Collector)
log_info "Applying Base Kustomize: corpshared-obs..."
${KUBECTL} apply -k "${REPO_ROOT}/platform/kustomize/base/corpshared-obs"

# 5. Deploy Management & Developer Portal (Backstage, Tekton Engine, ArgoCD Server)
log_info "Applying Base Kustomize: corpshared-mgmt..."
${KUBECTL} apply -k "${REPO_ROOT}/platform/kustomize/base/corpshared-mgmt"

log_success "Control plane base manifests successfully applied!"
log_info "Check pod status across enterprise namespaces using:"
log_info "  ${KUBECTL} get pods -n drr-corpshared-secr-internal"
log_info "  ${KUBECTL} get pods -n drr-corpshared-plat"
log_info "  ${KUBECTL} get pods -n drr-corpshared-obs"
log_info "  ${KUBECTL} get pods -n drr-corpshared-mgmt"
