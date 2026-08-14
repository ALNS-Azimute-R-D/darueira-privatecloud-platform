# darueira-operator

## Overview
Core Kubernetes Operator reconciling custom resources for the Darueira Private Cloud Platform.

## Responsibilities
- Reconciles Custom Resource Definitions (CRDs):
  - `Tenant` (`darueira.io/v1alpha1`)
  - `Project` (`darueira.io/v1alpha1`)
  - `Environment` (`darueira.io/v1alpha1`)
  - `TenantSecretMount` (`darueira.io/v1alpha1`)
- Provisions isolated tenant namespaces (`drr-tnt-{tenant}-{project}-{env}`).
- Automatically generates and enforces Cilium Network Policies (eBPF L3-L7 isolation).
- Binds OpenBao (Vault) roles and SPIRE workload registration entries.
- Injects ResourceQuotas, LimitRanges, and non-root security contexts.

## Tech Stack
- Go Lang (Kubebuilder / controller-runtime)
- Cilium Go Client
- OpenBao / Vault Go SDK
- SPIRE Server API Client
