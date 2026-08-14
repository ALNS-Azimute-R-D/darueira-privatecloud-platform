# Tekton CI Pipelines

## Overview
Declarative In-Cluster CI Pipelines for building, testing, scanning, and publishing container images and Helm charts in the Darueira Private Cloud.

## Standard Pipeline Stages
1. **Source Clone**: Git fetch via SSH / deploy key.
2. **Build & Unit Test**: Polyglot builders (Maven/Gradle for Java 25 & Kotlin, Go toolchain, Node/NPM for Backstage/React).
3. **Security Scan**: Vulnerability scanning via Trivy / Grype; SAST linting.
4. **Container Build**: Kaniko / Buildah unprivileged non-root container image build.
5. **Registry Push**: Push tagged images to Sonatype Nexus OSS / Local MicroK8s registry.
6. **Artifact Storage**: Persistent pipeline logs and artifacts saved to Central MinIO.
