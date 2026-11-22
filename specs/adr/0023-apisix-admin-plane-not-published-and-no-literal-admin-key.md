# ADR 0023: APISIX Admin Plane Not Published, Admin Key from a Secret

## Status
Accepted (2026-11-23). Applies the Zero Trust guardrail of `AGY.md` ("never expose administrative endpoints without route policies and
mTLS/OIDC validation") to the gateway itself. Complements ADR-0022.

## Context
- The Service `apisix-gateway` is `type: NodePort` and listed the Admin API (9180) and the metrics (9091) among its ports. Kubernetes
  gave each of them a port on the host: the Admin API answered on the LAN address of the host (`<host>:30087`, HTTP 401 without a key).
  The Admin API can rewrite every route of the platform.
- The only protection was the admin key, a literal in `apisix-gateway.yaml` and, until backlog item 51, in scripts: it is in the Git history.
- `allow_admin` was `0.0.0.0/0`.
- Every legitimate user of the Admin API (`make bootstrap-apisix`, `check-apisix-routes`, `smoke-apisix-upstreams`,
  `bootstrap_observability.py`) already reaches it through `kubectl port-forward`, which connects from `127.0.0.1` inside the pod.

## Decision
1. **The admin plane is not published.** `apisix-gateway` (NodePort) keeps only the data plane (80, 443, 9080, 9443). A new ClusterIP Service,
   `apisix-gateway-internal`, carries the Admin API (9180) and the metrics (9091); Prometheus scrapes it, operators use
   `kubectl port-forward svc/apisix-gateway-internal 9180:9180`.
2. **`allow_admin` is `127.0.0.1/32`.** Any other source gets HTTP 403 before the key is even checked.
3. **The admin key is not in Git.** `config.yaml` reads `${{APISIX_ADMIN_KEY}}`, injected from the Secret `apisix-secrets` (key `admin-key`,
   created by `scripts/provision_apisix_secrets.py`).

## Consequences
- **Positive:** the Admin API is no longer reachable from the LAN nor from other pods; the key is out of the manifest.
- **Cost:** the gateway pod was replaced once (rolling, a few seconds of connection refusals while the new pod loaded its routes).
- **Not done:** the key that lives in the Git history is unchanged (André decided not to rotate it for now); until it is rotated it must
  be treated as known, which `allow_admin` and the closed port now compensate.
