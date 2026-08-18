#!/usr/bin/env bash
# ==============================================================================
# Script: import_opensearch_dashboards.sh
# Project: darueira-privatecloud-platform
# Description: Generates and imports OpenSearch Dashboards saved objects
#              (Index Patterns, Saved Searches, Visualizations, Dashboards).
# ==============================================================================

set -euo pipefail

# ANSI Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo -e "${CYAN}================================================================${NC}"
echo -e "${CYAN}  Darueira Platform - OpenSearch Dashboards Provisioner         ${NC}"
echo -e "${CYAN}================================================================${NC}"

# Determine Kubernetes CLI tool
if command -v kubectl &>/dev/null; then
    KUBECTL="kubectl"
elif command -v microk8s &>/dev/null; then
    KUBECTL="microk8s kubectl"
else
    echo -e "${RED}[ERROR] Neither kubectl nor microk8s found.${NC}" >&2
    exit 1
fi

echo -e "${BLUE}[INFO] Generating latest OpenSearch saved objects bundle...${NC}"
python3 "${REPO_ROOT}/scripts/generate_opensearch_saved_objects.py"

DASHBOARDS_FILE="${REPO_ROOT}/platform/kustomize/base/corpshared-obs/dashboards/opensearch-saved-objects.ndjson"

if [ ! -f "${DASHBOARDS_FILE}" ]; then
    echo -e "${RED}[ERROR] Dashboards bundle file not found: ${DASHBOARDS_FILE}${NC}" >&2
    exit 1
fi

echo -e "${BLUE}[INFO] Applying Observability Kustomize manifests to cluster...${NC}"
${KUBECTL} apply -k "${REPO_ROOT}/platform/kustomize/base/corpshared-obs"

echo -e "${BLUE}[INFO] Waiting for OpenSearch Dashboards pod to be ready...${NC}"
${KUBECTL} wait --namespace drr-corpshared-obs \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/name=opensearch-dashboards \
  --timeout=120s

DASHBOARDS_POD=$(${KUBECTL} get pod -n drr-corpshared-obs -l app.kubernetes.io/name=opensearch-dashboards -o jsonpath="{.items[0].metadata.name}")

echo -e "${BLUE}[INFO] Target pod: ${DASHBOARDS_POD}${NC}"
echo -e "${BLUE}[INFO] Uploading and importing saved objects bundle...${NC}"

${KUBECTL} cp "${DASHBOARDS_FILE}" "drr-corpshared-obs/${DASHBOARDS_POD}:/tmp/opensearch-saved-objects.ndjson" -c opensearch-dashboards

IMPORT_OUTPUT=$(${KUBECTL} exec -n drr-corpshared-obs "${DASHBOARDS_POD}" -c opensearch-dashboards -- \
    curl -s -X POST "http://localhost:5601/api/saved_objects/_import?overwrite=true" \
    -H "osd-xsrf: true" \
    --form file=@/tmp/opensearch-saved-objects.ndjson)

echo -e "${GREEN}[SUCCESS] Saved objects import result:${NC}"
echo "${IMPORT_OUTPUT}" | jq . || echo "${IMPORT_OUTPUT}"

echo -e "${BLUE}[INFO] Setting default index pattern to darueira-k8s-logs...${NC}"
${KUBECTL} exec -n drr-corpshared-obs "${DASHBOARDS_POD}" -c opensearch-dashboards -- \
    curl -s -X POST "http://localhost:5601/api/opensearch-dashboards/settings/defaultIndex" \
    -H "osd-xsrf: true" \
    -H "Content-Type: application/json" \
    -d '{"value": "darueira-k8s-logs"}' > /dev/null

echo -e "\n${GREEN}================================================================${NC}"
echo -e "${GREEN}  OpenSearch Dashboards & Saved Searches successfully ready!    ${NC}"
echo -e "${GREEN}================================================================${NC}"
echo -e "Access via APISIX: ${CYAN}http://logs.darueira-corpshared.127.0.0.1.nip.io:30080${NC} or ${CYAN}http://127.0.0.1:5601${NC}"
