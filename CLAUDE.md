# CLAUDE.md — darueira-privatecloud-platform

Shared project rules live in `AGY.md` (also followed by the Antigravity agent). They apply to
Claude as well: SDD first (`specs/`, `authz/schema.fga`), Zero Trust, corpshared/tenant trust
domain separation, and the security guardrails.

@AGY.md

---

## Multi-agent collaboration (Claude + Antigravity + André)

- **Task board**: `docs/roadmap/backlog-melhorias.md`. Before starting an item, mark its owner
  (Claude / AGY / André) and status there. Never pick an item owned by someone else.
- **Git isolation**: each agent works on its own branch or worktree. Do not edit files another
  agent is working on in the same working tree. If a file changed on disk unexpectedly, stop and
  ask instead of overwriting it.
- **Single writer on the cluster**: only one agent at a time runs mutating cluster actions
  (`kubectl apply/delete/rollout restart`, Cilium agent restart, DB cleanups, NiFi changes,
  triggering import workflows). Read-only diagnosis (get/describe/logs) can run in parallel.
- **Handoff notes**: when finishing an item, record in the backlog what changed, the commit(s),
  and what is still unvalidated.

## Repository conventions

- This platform repo is **not GitOps**: commit directly to `master`; André pushes to GitHub.
- Tenant business apps (`workspace/platf-bizz-apps/...`) are **full GitOps** via the internal
  Forgejo: feature branch → PR → merge to `master` → Tekton builds and promotes the image tag in
  the chart repo → ArgoCD syncs.
- `scripts/bootstrap_apisix_routes.py` is the single source of truth for APISIX routes
  (`make check-apisix-routes` detects drift; `make smoke-apisix-upstreams` probes upstreams).
- NiFi `ExecuteScript` bodies are versioned in `platform/nifi/` and applied with
  `scripts/apply_nifi_script_body.py` (`--check` reports drift). Do not edit them only in the UI.
- Operational findings go to `docs/runbooks/` (e.g. `cilium-cni-migration.md` "achados críticos").

## Environment gotchas

- Commands needing `sudo` cannot be run from the agent (no TTY for the password): hand them to
  André to run in his own terminal.
- Host DNS does not resolve `*.nip.io` (FritzBox DNS rebind protection). Test gateway routes via
  the APISIX NodePort: `curl -H "Host: <route-host>" http://127.0.0.1:30080/...`.
- After any `microk8s stop`/`start` or reboot, check the Cilium IPAM (`cilium-dbg status | grep IPAM`
  ≈ number of pods) and `journalctl -t cilium-state-cleanup`; see runbook achado crítico #7.
- Live state can differ from `AGY.md`/specs (e.g. Cilium runs with `KubeProxyReplacement: False`
  on 1.15.2). Verify against the cluster before relying on the spec.
- Never delete reference data (continents/regions in `tb_geo_location`) when cleaning test data:
  country imports depend on it.
