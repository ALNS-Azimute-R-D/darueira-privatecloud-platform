# 8. Enterprise Message Brokers: Kafka/Redpanda with Kafbat UI and RabbitMQ 4

Date: 2026-08-17

## Status

Accepted

## Context

The Darueira Private Cloud Platform requires dual asynchronous messaging capabilities across the Enterprise Shared Services tier (`drr-corpshared-plat`):
1. **Event Streaming & ReBAC Tuple Replication**: High-throughput distributed commit log (Kafka protocol) for ReBAC tuple mutation events (`drr.authz.*`), audit trails, and platform telemetry.
2. **Visual Kafka Administration**: Low-overhead, open-source web console to inspect topics, consumer groups, schemas, and live message streams without requiring desktop tools.
3. **Enterprise AMQP Message Brokering**: Traditional message broker with fine-grained exchanges, routing keys, dead-letter exchanges, and task queuing (RabbitMQ 4.x) with integrated Web Management console.
4. **Zero Trust & Network Isolation**: Strict enforcement of Kubernetes PSS `restricted` profiles and Cilium L3/L7 Network Policies.

## Decision

1. **Renaming & Restructuring Kafka Pod to `message-broker-kafka`**:
   - Rename the deployment and service from generic `message-broker` to **`message-broker-kafka`**.
   - Standardize Redpanda Kafka broker (`docker.redpanda.com/redpandadata/redpanda:v24.1.8`) with advertise address `PLAINTEXT://message-broker-kafka.drr-corpshared-plat.svc.cluster.local:9092`.

2. **Embedding Kafbat UI as an In-Pod Sidecar**:
   - Deploy **Kafbat UI** (`ghcr.io/kafbat/kafka-ui:latest`) as a sidecar container inside the `message-broker-kafka` Pod.
   - Connect Kafbat UI directly to `127.0.0.1:9092` for zero-latency in-pod cluster communication.
   - Expose Kafbat UI on port `8080` via service `message-broker-kafka`.

3. **Deploying RabbitMQ 4 (`message-broker-rabbitmq`)**:
   - Deploy **RabbitMQ 4** (`rabbitmq:4-management-alpine`) with management plugin enabled.
   - Expose AMQP protocol on port `5672` and HTTP Management Console on port `15672`.
   - Persist state via `PersistentVolumeClaim` (`message-broker-rabbitmq-pvc`, 5Gi) mounted to `/var/lib/rabbitmq`.
   - Run as non-root UID `999` with default administrative credentials (`drr_admin` / `darueira-admin123`).

4. **Edge Ingress Routing via Apache APISIX**:
   - Expose **Kafbat UI** at `https://kafka.darueira-corpshared.127.0.0.1.nip.io` (and alias `kafbat.*`).
   - Expose **RabbitMQ Management** at `https://rabbitmq.darueira-corpshared.127.0.0.1.nip.io`.

5. **Cilium Network Security**:
   - Authorize ingress ports `9092` (Kafka), `9644` (Redpanda Admin), `5672` (AMQP), `15672` (RabbitMQ Mgmt), and `8080` (Kafbat UI) in `network-policy.yaml`.

## Consequences

- **Comprehensive Messaging Support**: Supports both modern event streaming (Kafka/Redpanda) and robust task queues / AMQP routing (RabbitMQ 4).
- **Self-Service Operator Experience**: Developers can inspect Kafka topics and RabbitMQ queues directly via clean browser URLs without CLI port-forwards.
- **Resource Efficiency**: Embedding Kafbat UI inside the Redpanda pod eliminates inter-pod network hops and reduces service definitions.
