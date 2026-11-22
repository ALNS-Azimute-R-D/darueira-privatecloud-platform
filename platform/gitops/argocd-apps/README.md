# ArgoCD GitOps Applications

## Overview
Declarative Continuous Delivery Application definitions and ApplicationSets for reconciling desired platform and tenant states in the Darueira Private Cloud.

## Root Applications
- `appprojects.yaml`: AppProjects (governance boundaries).
- `apps-swfabrik-*.yaml`: tenant business applications (GitOps via Forgejo chart repos).

> The `corpshared-*` Applications were removed (2026-11-22): they only managed a placeholder `tier-profile` ConfigMap. Corporate shared infrastructure is PaaS, managed via Kustomize/`kubectl` (ADR-0016), not ArgoCD.

- `applicationset-tenants.yaml`: ApplicationSet dynamically provisioning applications for every active tenant environment.
