# 6. Stalwart Corporate Mail Server Architecture, Storage Backend, and Ingress Integration

Date: 2026-08-17

## Status

Accepted

## Context

The Darueira Private Cloud Platform requires a self-hosted, cloud-native Corporate Mail Server and Communication Suite supporting:
1. Modern and legacy email protocols: SMTP (25), Submission (587), SMTPS (465), IMAPS (993), POP3S (995), ManageSieve (4190), and JMAP.
2. Web-based administrative console for domain, account, queue, and security policy management.
3. Decoupled and resilient storage architecture avoiding ephemeral local storage and integrating with the Central Control Plane persistence tier (PostgreSQL).
4. Strict compliance with Kubernetes `restricted` Pod Security Standards (PSS) without running privileged containers.
5. Secure edge exposure via Apache APISIX Gateway with wildcard DNS (`*.darueira-corpshared.127.0.0.1.nip.io`) and TLS termination.

## Decision

1. **Standardization on Modern Stalwart Mail Server (`stalwartlabs/stalwart`)**:
   - Migrate from legacy `stalwartlabs/mail-server:v0.8.0` to the official repository `stalwartlabs/stalwart:latest` (v0.16.x+).
   - Align backend API with the bundled Stalwart WebAdmin interface to prevent client-server schema mismatches (HTTP 400 Bad Request errors).

2. **Decoupled Relational Storage & Configuration Bootstrap**:
   - Persist server state, metadata, domains, and accounts in the **Central PostgreSQL** instance (`central-postgres.drr-corpshared-plat.svc.cluster.local:5432`) under the dedicated database `drr_stalwart_mailserver_db`.
   - Mount a declarative `ConfigMap` (`stalwart-config`) to `/etc/stalwart/config.json` defining the PostgreSQL database pointer.
   - Attach a `PersistentVolumeClaim` (`stalwart-mail-pvc`, 5Gi) to `/var/lib/stalwart` for local working directories and MTA queues.

3. **Kubernetes Security Context & Network Capabilities**:
   - Run the container as unprivileged non-root user (`UID/GID 2000`) matching the Stalwart base image.
   - Add the Linux kernel capability `NET_BIND_SERVICE` within the container's `securityContext` to allow unprivileged binding to standard low-numbered ports (25, 465, 587, 993, 4190) under Kubernetes PSS `restricted` profiles.
   - Update `CiliumNetworkPolicy` (`default-deny-and-plat-rules`) in `drr-corpshared-plat` to permit ingress traffic on ports `8080`, `25`, `465`, `587`, and `993`.

4. **Edge Routing via Apache APISIX**:
   - Expose the Stalwart WebAdmin and JMAP interface via APISIX route `route-host-stalwart-mail` pointing to `stalwart-mail.drr-corpshared-plat.svc.cluster.local:8080`.
   - Bind hostnames `mail.darueira-corpshared.127.0.0.1.nip.io` and `stalwart.darueira-corpshared.127.0.0.1.nip.io` with wildcard TLS termination.

5. **Recovery & Bootstrap Administration**:
   - Support fixed recovery credentials via `STALWART_RECOVERY_ADMIN="admin:darueira-admin123"` environment variable to guarantee deterministic administrative access.

## Consequences

- **High Reliability**: Restarting or updating the Stalwart Pod preserves all domains, accounts, and cryptographic keys stored safely in Central PostgreSQL.
- **Security Compliance**: Runs safely in hardened MicroK8s namespaces with non-root UID and specific `NET_BIND_SERVICE` privilege without full root escalation.
- **Unified Access**: Developers and operators access the Mail Admin Console via standard platform ingress without manual port-forwarding.
