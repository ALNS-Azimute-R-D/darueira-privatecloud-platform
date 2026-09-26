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

## BookAnything backend: JVM and native image variants

Every push to `master` of `bookanything-platform` (the `bookanything-events` trigger in
`triggers-forgejo-integration.yaml`) builds the backend, and the **variant** is chosen from the
**subject (first line) of the pushed commit**:

| Subject contains | Dockerfile | Image tag | Notes |
|------------------|------------|-----------|-------|
| nothing (default) | `Dockerfile.jvm` | `YYYY.MMDD.HHMMSS-jvm` | Fast (~6 min). Use it to iterate on features. |
| `[native]` (any case) | `Dockerfile.native` | `YYYY.MMDD.HHMMSS-native` | GraalVM native image. ~20 min when the sources changed, ~4 min when the Kaniko layer cache hits. Use it for releases and to validate native-only problems (reflection hints). |

- **Put `[native]` in the PR title.** On a merge Forgejo copies the title to the subject of the merge
  commit (`Merge pull request '<title>' (#n) from ... into master`); on a squash the title is the
  subject. Use "Merge commit" or "Squash": with "Rebase" the title is lost and the build is JVM.
  A `[native]` in the body of the message is ignored.
- The CEL expression is an overlay of the trigger (`extensions.image_variant`), passed to the template
  as `image-variant`, which sets `dockerfile-path: Dockerfile.<variant>` and `image-tag: auto-<variant>`.
  `task-kaniko-build` turns `auto-<suffix>` into `<timestamp>-<suffix>`; a plain `auto` still means
  just the timestamp. The frontend PipelineRun is unchanged (`auto`, `Dockerfile`).
- The **chart derives the Pod settings from the tag suffix** (memory, `JAVA_TOOL_OPTIONS`, probes): see
  the README of `bookanything-platform-chart`.
- **Safety net to know about:** `task-kaniko-build` does not fail when the Dockerfile is missing, it
  builds a placeholder Alpine image and the pipeline goes on. A variant whose Dockerfile does not
  exist would therefore deploy a placeholder container. Both `Dockerfile.jvm` and `Dockerfile.native`
  exist in `1-backends/bookanything-monolith-backend-01`.
- Manual run: `pipelineruns-swfabrik-europe.yaml` has a template (`...-backend-manual`) with the
  `Dockerfile.jvm` / `auto-jvm` pair and a comment for the native one.
- Tested against the real Tekton CEL interceptor with a Forgejo push payload: a merge commit without the
  mark gives `jvm`; `[native]` in the title (merge or squash) gives `native`; `[native]` only in the
  body gives `jvm`; a push to another branch is filtered out.
