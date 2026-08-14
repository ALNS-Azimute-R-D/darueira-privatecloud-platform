# 5. Enterprise Observability, PKI, and Messaging Stack

Date: 2026-08-15

## Status

Accepted

## Context

The Darueira Private Cloud Platform requires a unified infrastructure foundation supporting:
1. **Automated PKI & TLS Certificates**: Secure certificate issuance across Ingress controllers, internal gRPC endpoints, and service-to-service communication.
2. **Enterprise Identity & Access Management (IdP)**: Keycloak (or Authentik) for centralized OIDC/OAuth2 authentication, user directory management, and multi-tenant realm federation.
3. **Event Streaming & Asynchronous Messaging**: High-throughput message broker (Kafka/Redpanda) for event-driven tuple mutations (`drr.authz.tuple-events`), audit logging, and tenant event streams.
4. **Comprehensive Observability & Telemetry**:
   - **Metrics**: Prometheus scraping Kubernetes nodes, control plane components, and tenant pods.
   - **Visualization**: Grafana with pre-configured operational and security dashboards.
   - **Logs**: OpenSearch for structured search, log aggregation, and compliance auditing.
   - **Traces**: Jaeger for end-to-end distributed tracing across Envoy PEP, OPA PDP, Gateway, and application microservices.
   - **Telemetry Pipeline**: OpenTelemetry (OTEL) Collector standardizing OTLP ingestion (gRPC 4317, HTTP 4318) and in-pod OTEL instrumentation.

## Decision

1. **PKI & Certificate Management**:
   - Deploy `cert-manager` in `drr-corpshared-secr-internal` with `ClusterIssuer` definitions backed by OpenBao (Vault PKI engine) and internal SelfSigned/CA issuers.
2. **Enterprise Identity Provider**:
   - Standardize on **Keycloak / Authentik** in `drr-corpshared-plat` connected to Central PostgreSQL 17 for realm persistence.
3. **Message Broker**:
   - Deploy a cloud-native **Kafka / Redpanda** broker in `drr-corpshared-plat` backed by host storage/PVC and MinIO tiered storage.
4. **Observability Tier (`drr-corpshared-obs`)**:
   - Deploy **Prometheus**, **Grafana**, **OpenSearch**, **Jaeger**, and **OpenTelemetry Collector**.
   - Standardize Pod telemetry export to the local OTEL Collector via OTLP (`http://otel-collector.drr-corpshared-obs.svc.cluster.local:4317`).
5. **In-Pod Telemetry & Sidecar Integration**:
   - Inject the OTEL exporter configuration into `workload-sidecar-patch.yaml` alongside the Envoy PEP and OPA PDP containers.

## Consequences

- **Observability Uniformity**: All platform components and tenant workloads export standardized OpenTelemetry signals (traces, metrics, logs).
- **Automated Encryption**: Zero manual TLS certificate renewals; cert-manager automates issuance and rotation.
- **Event-Driven Decoupling**: High-speed asynchronous replication of IAM tuple mutations and platform state changes via Kafka.
- **Resource Footprint**: All observability components run with non-root security contexts (`USER 10001`) and tuned memory limits suitable for laptop/MicroK8s development.
