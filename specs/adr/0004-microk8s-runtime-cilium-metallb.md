# ADR 0004: MicroK8s Runtime with Cilium CNI and MetalLB

## Status
Accepted

## Context
The platform must run efficiently on local developer workstations (Linux Mint 22.3, Intel i9, 64 GB RAM) while supporting production-grade cloud-native features:
- eBPF-based L3-L7 NetworkPolicies and high performance routing;
- Transparent node encryption via WireGuard;
- LoadBalancer service provisioning via MetalLB IP pools;
- Strict non-root security standards (`USER 10001`, `runAsNonRoot: true`).

## Decision
Adopt Canonical MicroK8s as the local Kubernetes runtime, paired with Cilium CNI (replacing standard iptables / kube-proxy where applicable) and MicroK8s MetalLB addon for LoadBalancer IP address allocation.

## Consequences
- Fast local bootstrapping and low overhead compared to heavy multi-node VMs.
- Enterprise-grade networking, security policies, and observability ready for hybrid extension (e.g. remote VPS).
