# ArgoCD GitOps Applications

## Overview
Declarative Continuous Delivery Application definitions and ApplicationSets for reconciling desired platform and tenant states in the Darueira Private Cloud.

## Root Applications
- `apps-corpshared-mgmt.yaml`: ArgoCD Application targeting `platform/kustomize/base/corpshared-mgmt`
- `apps-corpshared-plat.yaml`: ArgoCD Application targeting `platform/kustomize/base/corpshared-plat`
- `apps-corpshared-secr-internal.yaml`: ArgoCD Application targeting `platform/kustomize/base/corpshared-secr-internal`
- `applicationset-tenants.yaml`: ApplicationSet dynamically provisioning applications for every active tenant environment.
