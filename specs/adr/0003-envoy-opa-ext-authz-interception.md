# ADR 0003: Envoy Proxy and OPA Sidecar Ext Authz Interception

## Status
Accepted

## Context
In a multi-tenant Zero Trust Kubernetes environment, application containers must be protected from unauthorized access at the pod ingress boundary before any business logic executes. Embedding authorization logic directly into every polyglot application (Java, Kotlin, Go, TypeScript) creates high maintenance overhead, introduces bypass vulnerabilities, and couples application code to authorization engines.

We need a standardized, language-agnostic, low-latency, and fail-closed interception architecture that separates:
1. **Policy Enforcement Point (PEP)**: Intercepting incoming L7 network traffic;
2. **Policy Decision Point (PDP)**: Evaluating fine-grained context, attributes, and relationship policies.

## Decision
We adopt **Envoy Proxy** as the in-pod Policy Enforcement Point (PEP) paired with **Open Policy Agent (OPA)** as the Policy Decision Point (PDP), utilizing Envoy's standard `envoy.filters.http.ext_authz` extension over local loopback gRPC (`127.0.0.1:9191`).

### 1. Ingress Request Flow
$$\text{Client / Ingress} \longrightarrow \text{Envoy PEP (:8000)} \xrightarrow[\text{gRPC :9191}]{\text{ext\_authz}} \text{OPA PDP} \xrightarrow[\text{gRPC / HTTP}]{\text{Check}} \text{OpenFGA} \longrightarrow \text{Envoy} \longrightarrow \text{App (:8080)}$$

1. **Ingress Interception**: Ingress traffic to the Pod is received on Envoy's listener (`0.0.0.0:8000`).
2. **gRPC ext_authz Evaluation**: Envoy extracts request metadata (HTTP method, path, headers, client identity, SPIFFE ID, body snippet up to 8KB) and sends an `AuthorizationRequest` to OPA over gRPC at `127.0.0.1:9191`.
3. **Policy Evaluation (PDP)**: OPA evaluates local Rego policy bundles. If relationship graph evaluation is needed, OPA queries the OpenFGA authorization engine (`drr-iam-authz-svc`).
4. **Decision & Routing**:
   - If OPA returns `OK (status: 0)`, Envoy forwards the request to the collocated application container at `127.0.0.1:8080`.
   - If OPA returns `PERMISSION_DENIED` or error, Envoy immediately terminates the request with `403 Forbidden` or `503 Service Unavailable`.

### 2. Failure Threshold & Timeout Boundaries
- **gRPC Timeout Limit**: Configured strictly to `0.25s` (250ms) to ensure deterministic latency and prevent cascading connection starvation.
- **Fail-Closed Security**: `failure_mode_allow: false` is strictly enforced. If OPA is unreachable, booting, or times out, Envoy rejects the request with HTTP `503 Service Unavailable`.

### 3. Enforcement Scope
- **Custom Platform Services** (`drr-tenant-svc`, `drr-iam-authz-svc`, `drr-env-orchestrator-svc`): Full Envoy PEP + OPA PDP sidecar injection.
- **Tenant Workload Pods**: Full Envoy PEP + OPA PDP sidecar injection.
- **COTS Shared Services** (Nexus, Stalwart, MinIO, OpenBao, Authentik): Protected at the cluster edge via APISIX API Gateway + OpenFGA plugins and Cilium L7 Network Policies.

## Consequences
- **Zero Bypass**: Application code cannot be reached without passing through Envoy PEP and OPA PDP evaluation.
- **Polyglot Consistency**: Consistent authorization semantics across Java, Kotlin, Go, Python, and TypeScript services.
- **Low Overhead**: Local loopback communication (`127.0.0.1`) minimizes latency overhead (< 1ms for local cache hits).
