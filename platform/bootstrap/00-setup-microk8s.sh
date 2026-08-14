#!/usr/bin/env bash
# ==============================================================================
# Script: 00-setup-microk8s.sh
# Project: darueira-privatecloud-platform
# Description: Configures MicroK8s addons, Cilium CNI, and MetalLB IP range.
# ==============================================================================

set -euo pipefail

# ANSI Color Codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

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
    echo -e "${CYAN}  Darueira Private Cloud - MicroK8s Foundation Setup            ${NC}"
    echo -e "${CYAN}================================================================${NC}"
}

log_banner

# 1. Verify MicroK8s Installation
log_info "Verifying MicroK8s installation..."
if ! command -v microk8s &>/dev/null; then
    log_error "MicroK8s is not installed. Please install it with: sudo snap install microk8s --classic"
    exit 1
fi

# 2. Check MicroK8s Status
log_info "Checking MicroK8s cluster status..."
microk8s status --wait-ready || {
    log_error "MicroK8s is not running or not ready."
    exit 1
}
log_success "MicroK8s cluster is active and ready."

# 3. Enable Core Addons
log_info "Enabling core MicroK8s addons (dns, hostpath-storage, rbac, registry)..."
microk8s enable dns hostpath-storage rbac registry

# 4. Configure MetalLB Ingress IP Range
# Default local network range (fallback to 192.168.1.240-192.168.1.250 if not specified)
METALLB_IP_RANGE="${METALLB_IP_RANGE:-192.168.1.240-192.168.1.250}"
log_info "Configuring MetalLB with IP Range: ${METALLB_IP_RANGE}..."
microk8s enable metallb:"${METALLB_IP_RANGE}" || {
    log_warn "MetalLB enable command returned a warning or is already enabled with an existing pool."
}

# 5. Cilium CNI Verification & Setup
log_info "Checking Cilium CNI integration..."
if microk8s status | grep -q "cilium: enabled"; then
    log_success "Cilium CNI is already enabled in MicroK8s."
elif command -v cilium &>/dev/null; then
    log_info "Cilium CLI found at $(command -v cilium). Checking status..."
    cilium status --wait || log_warn "Cilium status check timed out or needs cluster init."
else
    log_info "Enabling Cilium addon in MicroK8s or installing Cilium CLI..."
    microk8s enable cilium || {
        log_warn "Standard MicroK8s cilium addon requires manual kubeconfig export or Cilium CLI helm install."
        log_info "To install Cilium manually via Helm or CLI:"
        log_info "  CILIUM_CLI_VERSION=\$(curl -s https://raw.githubusercontent.com/cilium/cilium-cli/main/stable.txt)"
        log_info "  curl -L --fail --remote-name-all https://github.com/cilium/cilium-cli/releases/download/\${CILIUM_CLI_VERSION}/cilium-linux-amd64.tar.gz"
    }
fi

log_success "MicroK8s Foundation Setup complete!"
log_info "You can now run 'make bootstrap-control-plane' or 'platform/bootstrap/01-deploy-control-plane.sh'."
