# drr-ctlr-cli

## Overview
Unified Platform Command-Line Interface for the Darueira Private Cloud Platform.

## Responsibilities
- Developer workflow interactions (login, project creation, environment deployment, secret injection).
- Platform administration (tenant onboarding, quota adjustments, operator health inspection).
- Local MicroK8s bootstrapping and diagnostic utilities.
- Direct invocation of OpenFGA authorization checks and validation of local specs.

## Tech Stack
- Go Lang (Cobra CLI framework, Viper configuration)
- OpenFGA CLI SDK
- Kubernetes client-go
