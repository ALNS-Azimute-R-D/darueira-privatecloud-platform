# drr-env-orchestrator-svc

## Overview
Environment Engine & Orchestration Service for the Darueira Private Cloud Platform.

## Responsibilities
- Receives declarative environment provisioning specifications (Dev, Staging, Prod).
- Generates and reconciles Kubernetes Custom Resources (CRDs) for the `darueira-operator`.
- Triggers Tekton PipelineRuns for building and testing application components.
- Manages ArgoCD ApplicationSets and GitOps state sync for tenant environments.
- Manages namespace provisioning (`drr-tnt-{tenant}-{project}-{env}`), resource quotas, and LimitRanges.

## Tech Stack
- Go Lang (Kubernetes client-go & controller-runtime)
- Tekton Client Go SDK
- ArgoCD API Client
