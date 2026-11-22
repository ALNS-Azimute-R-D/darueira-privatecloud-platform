#!/usr/bin/env bash
# Runs authz/tests.fga.yaml (the ReBAC assertions of the SDD) against the live OpenFGA with the official fga CLI image.
# The CLI creates and deletes throw-away stores, so the real store and its tuples are not touched. (ADR-0021)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${OPENFGA_LOCAL_PORT:-18081}"
kubectl -n drr-corpshared-plat port-forward svc/openfga "${PORT}:8080" >/dev/null 2>&1 &
PF=$!
trap 'kill $PF 2>/dev/null || true' EXIT
for _ in $(seq 1 20); do curl -fs "http://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1 && break || sleep 1; done
docker run --rm --network host -v "${ROOT}/authz":/authz:ro "${FGA_CLI_IMAGE:-openfga/cli:latest}" \
  --api-url "http://127.0.0.1:${PORT}" model test --tests /authz/tests.fga.yaml
