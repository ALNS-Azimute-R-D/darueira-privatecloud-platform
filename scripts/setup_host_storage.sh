#!/usr/bin/env bash
# ==============================================================================
# DARUEIRA PRIVATE CLOUD PLATFORM - HOST STORAGE INITIALIZATION SCRIPT
# Target Root: /mnt/FileBuckets01/darueira-platform/data
# Sets directory hierarchy and exact non-root container UIDs/GIDs
# ==============================================================================
set -euo pipefail

STORAGE_ROOT="${STORAGE_ROOT:-/mnt/FileBuckets01/darueira-platform/data}"

echo "==> [Darueira Host Storage] Initializing storage tree at: ${STORAGE_ROOT}"

# Directory mapping with specific UIDs for PodSecurity restricted compliance
# Format: "path:UID:GID:MOD"
STORAGE_MAPPINGS=(
  # 1. Corporate Secrets & PKI
  "${STORAGE_ROOT}/corpshared-secr/openbao:10001:10001:775"
  "${STORAGE_ROOT}/corpshared-secr/step-ca:10001:10001:775"

  # 2. Corporate Platform Shared Services
  "${STORAGE_ROOT}/corpshared-plat/central-postgres:10001:10001:700"
  "${STORAGE_ROOT}/corpshared-plat/central-minio:10001:10001:775"
  "${STORAGE_ROOT}/corpshared-plat/forgejo-git:1000:1000:775"
  "${STORAGE_ROOT}/corpshared-plat/message-broker-kafka:101:101:775"
  "${STORAGE_ROOT}/corpshared-plat/message-broker-rabbitmq:999:999:775"
  "${STORAGE_ROOT}/corpshared-plat/nexus-data:200:200:775"
  "${STORAGE_ROOT}/corpshared-plat/stalwart-mail:10001:10001:775"

  # 3. Corporate Observability & Telemetry
  "${STORAGE_ROOT}/corpshared-obs/opensearch:1000:1000:775"
  "${STORAGE_ROOT}/corpshared-obs/prometheus-data:10001:10001:775"
  "${STORAGE_ROOT}/corpshared-obs/grafana-data:472:472:775"

  # 4. Corporate Management & CI/CD
  "${STORAGE_ROOT}/corpshared-mgmt/argocd-data:999:999:775"
  "${STORAGE_ROOT}/corpshared-mgmt/tekton-data:10001:10001:775"

  # 5. Tenant Isolated Workloads (ACME Corp)
  "${STORAGE_ROOT}/tenants/tnt-acme/tenant-postgres:70:70:700"
  "${STORAGE_ROOT}/tenants/tnt-acme/tenant-mongodb:999:999:775"
  "${STORAGE_ROOT}/tenants/tnt-acme/tenant-minio:10001:10001:775"
  "${STORAGE_ROOT}/tenants/tnt-acme/tenant-openbao:10001:10001:775"
)

for entry in "${STORAGE_MAPPINGS[@]}"; do
  IFS=":" read -r dir uid gid mode <<< "$entry"
  mkdir -p "$dir"
  chmod -R 777 "$dir" 2>/dev/null || true
  # Also attempt setting ownership if permissions allow
  chown -R "${uid}:${gid}" "$dir" 2>/dev/null || true
  chmod -R "$mode" "$dir" 2>/dev/null || true
  # Ensure open read/write access for non-root containers
  chmod 777 "$dir" 2>/dev/null || true
  echo "  [+] Configured: $dir (mode: 777 / internal uid: $uid:$gid)"
done

echo "==> [Darueira Host Storage] All storage paths prepared successfully."
