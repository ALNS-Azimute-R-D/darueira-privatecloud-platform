# drr-iam-authz-svc

## Overview
Identity & Authorization Gateway Service for Darueira Private Cloud Platform.

## Responsibilities
- Intercepts API and Ingress traffic to perform fine-grained authorization checks.
- Validates OIDC JWT tokens and claims from Authentik / Keycloak.
- Evaluates Relationship-Based Access Control (ReBAC) tuples against OpenFGA (`authz/schema.fga`).
- Enforces multi-tenant isolation and role-based / relation-based permissions across Tenants, Projects, Environments, and Components.
- Integrates with Apache APISIX as an external authz plugin / forward auth service.

## Tech Stack
- Go Lang / Kotlin
- OpenFGA Go SDK
- SPIFFE/SPIRE Workload Attestation

## Observability
- **Metrics:** Prometheus text format at `GET /metrics` on `METRICS_PORT` (default `9102`). It is a separate listener on purpose:
  the APISIX route of this service forwards every path of the API port (`8080`), so metrics there would be published through
  the gateway. Only the in-cluster Prometheus (job `drr-iam-authz-svc`) scrapes it.
- **Series (`drr_iam_authz_*`):** `http_requests_total{method,route,code}`, `http_request_duration_seconds` (histogram),
  `http_requests_in_flight`, `decisions_total{endpoint,decision}` (`endpoint` = `check`, `batch_check`, `forward_auth`;
  `decision` = `allowed`, `denied`, `error`), `build_info{version}`, plus Go runtime and process metrics. The `route` label is the
  ServeMux pattern, never the raw path.
- **Dashboard:** Grafana "Darueira Security - IAM AuthZ Service" (`iam-authz-service`).
- **Tests and build without a local Go toolchain:** `docker run --rm -v "$PWD":/src -w /src golang:1.24-alpine go test ./...`.
  `prometheus/client_golang` is pinned to 1.23.x: 1.25 requires Go 1.26.
