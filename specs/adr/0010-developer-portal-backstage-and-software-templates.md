# 10. Internal Developer Portal: Spotify Backstage Architecture and Integrations

Date: 2026-08-17

## Status

Accepted

## Context

The Darueira Private Cloud Platform requires a centralized Internal Developer Portal (IDP) in the Management Shared Services plane (`drr-corpshared-mgmt`):
1. **Software Catalog & System Topology**: Unify visibility over platform microservices, tenant workloads, APIs, message queues (Redpanda/Kafka and RabbitMQ), and data schemas.
2. **Golden Path Scaffolding**: Provide reproducible Software Templates enabling developers to instantiate new service repositories (Spring Boot, Go, Node.js) with standard CI/CD pipelines, Dockerfiles, and K8s manifests in seconds.
3. **Ecosystem Integrations**: Centralize access to GitOps (ArgoCD), CI/CD (Tekton Pipelines), Internal Git (Forgejo), Central MinIO (TechDocs), Central PostgreSQL, and Kubernetes cluster topology.
4. **Optimized Resource Consumption**: Must operate efficiently in local developer workstation environments (< 600 MB RAM).

## Decision

1. **Deploying Pre-Compiled Backstage Showcase (`quay.io/janus-idp/backstage-showcase`)**:
   - Deploy **Backstage Showcase** (maintained by Red Hat Developer Hub / Janus IDP community) under deployment `backstage` in namespace `drr-corpshared-mgmt`.
   - Utilizes pre-compiled frontend React bundle and dynamic plugin loader, eliminating heavy Node.js build steps on developer machines while providing rich out-of-the-box plugin coverage.

2. **Declarative Runtime Configuration via ConfigMap**:
   - Provide `app-config.yaml` mounted to `/opt/app-root/src/app-config.yaml` configured for:
     - **Database**: Central PostgreSQL (`central-postgres.drr-corpshared-plat.svc.cluster.local:5432`) under database `drr_backstage_db` with automated plugin database provisioning (`backstage_plugin_catalog`, `backstage_plugin_scaffolder`, `backstage_plugin_auth`, `backstage_plugin_search`, etc.).
     - **Git Provider**: Internal Forgejo Git Server (`https://git.darueira-corpshared.127.0.0.1.nip.io`).
     - **GitOps Engine**: ArgoCD instance locator (`https://argocd.darueira-corpshared.127.0.0.1.nip.io`).
     - **Kubernetes Cluster Access**: In-cluster Kubernetes API (`https://kubernetes.default.svc`) via service account credentials.
     - **TechDocs**: Local/S3 storage publisher for technical documentation generation.
     - **Authentication & Security**: Dedicated JWT signing keys under `backend.auth.keys` for production inter-service verification.

3. **Kubernetes Security Context**:
   - Run as non-root UID `1001`, `runAsGroup: 1001`, `fsGroup: 1001` with `seccompProfile: RuntimeDefault` complying with Kubernetes `restricted` Pod Security Standards.

4. **Edge Ingress Routing via Apache APISIX**:
   - Expose the portal at `https://backstage.darueira-corpshared.127.0.0.1.nip.io` via route `route-host-backstage` forwarding to `backstage.drr-corpshared-mgmt.svc.cluster.local:7007`.

## Consequences

- **Single Pane of Glass**: Complete developer portal available with zero build overhead.
- **Low Footprint**: Consumes ~400 MB RAM and ~10m CPU at idle.
- **Seamless Local Golden Paths**: Direct template execution against local Forgejo Git and Tekton Pipelines without external SaaS dependencies.
