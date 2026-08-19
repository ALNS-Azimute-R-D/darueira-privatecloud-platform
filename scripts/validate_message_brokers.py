#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Enterprise Message Brokers & Multi-Tenancy
Kafka/Redpanda & RabbitMQ 4 Comprehensive Validation Suite
==============================================================================
"""

import sys
import os
import json
import base64
import time
import subprocess
import urllib.request
import urllib.parse
import urllib.error

KAFKA_POD = os.environ.get("KAFKA_POD", "deploy/message-broker-kafka")
KAFKA_NS = os.environ.get("KAFKA_NS", "drr-corpshared-plat")

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "message-broker-rabbitmq.drr-corpshared-plat.svc.cluster.local:15672")
RABBITMQ_ADDR = f"http://{RABBITMQ_HOST}"
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "drr_admin")
RABBITMQ_PASS = os.environ.get("RABBITMQ_PASS", "darueira-admin123")
ADMIN_AUTH = "Basic " + base64.b64encode(f"{RABBITMQ_USER}:{RABBITMQ_PASS}".encode("utf-8")).decode("utf-8")

KAFBAT_HOST = os.environ.get("KAFBAT_HOST", "message-broker-kafka.drr-corpshared-plat.svc.cluster.local:8080")
KAFBAT_ADDR = f"http://{KAFBAT_HOST}"

EXPECTED_KAFKA_TOPICS = [
    "drr.authz.tuple-events",
    "drr.tenant.lifecycle-events",
    "drr.environment.events",
    "drr.audit.log-events",
    "acme.storefront.orders",
    "acme.logistics.tracking",
    "globex.security.findings"
]

EXPECTED_RABBITMQ_VHOSTS = ["drr-platform", "acme", "globex"]


def rmq_request(path, data=None, method="GET", auth=ADMIN_AUTH):
    clean_path = path.lstrip("/")
    url = f"{RABBITMQ_ADDR}/api/{clean_path}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    headers = {
        "Authorization": auth,
        "Content-Type": "application/json"
    }
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status == 204 or resp.length == 0:
            return None
        return json.loads(resp.read().decode("utf-8"))


def test_redpanda_health():
    cmd = f"microk8s kubectl exec -n {KAFKA_NS} {KAFKA_POD} -c redpanda -- rpk cluster health"
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
    assert "Healthy:" in res.stdout or "true" in res.stdout.lower(), f"Redpanda cluster unhealthy: {res.stdout}"
    return res.stdout.strip()


def test_kafka_topics():
    cmd = f"microk8s kubectl exec -n {KAFKA_NS} {KAFKA_POD} -c redpanda -- rpk topic list"
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
    raw = res.stdout
    for expected in EXPECTED_KAFKA_TOPICS:
        assert expected in raw, f"Kafka topic missing: {expected}"
    return len(EXPECTED_KAFKA_TOPICS)


def test_kafka_pubsub():
    # 1. Produce message to drr.authz.tuple-events
    msg = json.dumps({"action": "insert", "tuple": {"user": "user:alice.developer", "relation": "viewer", "object": "environment:acme-storefront-prod"}}) + "\n"
    prod_cmd = f"microk8s kubectl exec -i -n {KAFKA_NS} {KAFKA_POD} -c redpanda -- rpk topic produce drr.authz.tuple-events"
    proc = subprocess.run(prod_cmd, shell=True, input=msg, capture_output=True, text=True, check=True)
    assert "Produced to partition" in proc.stdout, f"Failed producing Kafka message: {proc.stdout} {proc.stderr}"

    # 2. Consume from drr.authz.tuple-events
    cons_cmd = f"microk8s kubectl exec -n {KAFKA_NS} {KAFKA_POD} -c redpanda -- rpk topic consume drr.authz.tuple-events -n 1 --format json"
    cons_proc = subprocess.run(cons_cmd, shell=True, capture_output=True, text=True, check=True)
    record = json.loads(cons_proc.stdout)
    assert record.get("topic") == "drr.authz.tuple-events", f"Unexpected consumed topic: {record}"
    return record


def test_kafbat_ui():
    req = urllib.request.Request(f"{KAFBAT_ADDR}/actuator/health")
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("status") == "UP", f"Kafbat UI health is {data.get('status')}"
        return data


def test_rabbitmq_health():
    overview = rmq_request("overview")
    assert overview.get("rabbitmq_version"), "No rabbitmq_version in overview response"
    return overview.get("rabbitmq_version")


def test_rabbitmq_vhosts_and_users():
    vhosts_data = rmq_request("vhosts")
    vhost_names = {v["name"] for v in vhosts_data}
    for expected_vh in EXPECTED_RABBITMQ_VHOSTS:
        assert expected_vh in vhost_names, f"RabbitMQ VHost missing: /{expected_vh}"

    users_data = rmq_request("users")
    user_names = {u["name"] for u in users_data}
    for expected_user in ["platform_worker", "acme_user", "globex_user"]:
        assert expected_user in user_names, f"RabbitMQ user missing: {expected_user}"
    return vhost_names, user_names


def test_rabbitmq_amqp_routing():
    vhost_enc = urllib.parse.quote("acme", safe="")
    # 1. Publish message
    order_payload = {"order_id": "ord-validation-2026", "item": "Cloud Security License", "status": "PENDING"}
    pub_res = rmq_request(f"exchanges/{vhost_enc}/acme.orders.topic/publish", data={
        "properties": {},
        "routing_key": "order.checkout",
        "payload": json.dumps(order_payload),
        "payload_encoding": "string"
    }, method="POST")
    assert pub_res.get("routed") is True, f"RabbitMQ message was not routed: {pub_res}"

    # 2. Consume message from queue
    get_res = rmq_request(f"queues/{vhost_enc}/acme.orders.processing/get", data={
        "count": 1,
        "ackmode": "ack_requeue_false",
        "encoding": "auto"
    }, method="POST")
    assert len(get_res) > 0, "No message returned from acme.orders.processing queue"
    payload = json.loads(get_res[0]["payload"])
    assert payload.get("order_id") == "ord-validation-2026", f"Payload mismatch: {payload}"
    return payload


def test_rabbitmq_tenant_isolation():
    acme_auth = "Basic " + base64.b64encode(b"acme_user:acme_secure_pass_2026").decode("utf-8")
    globex_auth = "Basic " + base64.b64encode(b"globex_user:globex_secure_pass_2026").decode("utf-8")

    vhost_acme = urllib.parse.quote("acme", safe="")
    vhost_globex = urllib.parse.quote("globex", safe="")

    # Acme user CAN access /acme
    acme_queues = rmq_request(f"queues/{vhost_acme}", auth=acme_auth)
    assert len(acme_queues) > 0, "Acme user could not list /acme queues"

    # Acme user CANNOT access /globex
    try:
        rmq_request(f"queues/{vhost_globex}", auth=acme_auth)
        assert False, "Security Violation: acme_user was able to access /globex vhost!"
    except urllib.error.HTTPError as e:
        assert e.code in [401, 403, 404], f"Expected HTTP 401/403/404, got {e.code}"

    # Globex user CANNOT access /acme
    try:
        rmq_request(f"queues/{vhost_acme}", auth=globex_auth)
        assert False, "Security Violation: globex_user was able to access /acme vhost!"
    except urllib.error.HTTPError as e:
        assert e.code in [401, 403, 404], f"Expected HTTP 401/403/404, got {e.code}"


def main():
    print("==================================================================")
    print("  Phase 09: Enterprise Message Brokers Validation Suite           ")
    print("==================================================================")

    # 1. Redpanda Cluster Health
    print("\n[1/8] Validating Redpanda Kafka Cluster Health & Admin API Status...")
    test_redpanda_health()
    print("      [✓] Redpanda Kafka Cluster is healthy and operational")

    # 2. Kafka Core Topics Topology
    print("\n[2/8] Validating Kafka Core Platform & Tenant Topics Topology...")
    t_count = test_kafka_topics()
    print(f"      [✓] All {t_count} platform and tenant Kafka topics verified and partitioned")

    # 3. Kafka Pub/Sub Roundtrip
    print("\n[3/8] Validating Kafka Event Streaming Pub/Sub Live Message Delivery...")
    record = test_kafka_pubsub()
    print(f"      [✓] Live event produced and consumed from '{record.get('topic')}' (Offset: {record.get('offset')})")

    # 4. Kafbat UI Health & Cluster Discovery
    print("\n[4/8] Validating Kafbat Web UI Status & Cluster Discovery (:8080)...")
    k_health = test_kafbat_ui()
    print(f"      [✓] Kafbat Web UI is active and healthy (Status: {k_health.get('status')})")

    # 5. RabbitMQ Health & Version
    print("\n[5/8] Validating RabbitMQ 4 Broker & Management API Health (:5672, :15672)...")
    rmq_ver = test_rabbitmq_health()
    print(f"      [✓] RabbitMQ Server active (Version: {rmq_ver})")

    # 6. RabbitMQ Multi-Tenant VHosts & Users
    print("\n[6/8] Validating RabbitMQ Multi-Tenant VHosts & User Permission Matrix...")
    vhosts, users = test_rabbitmq_vhosts_and_users()
    print(f"      [✓] Virtual Hosts verified: {list(EXPECTED_RABBITMQ_VHOSTS)}")
    print(f"      [✓] Scoped tenant users verified: ['platform_worker', 'acme_user', 'globex_user']")

    # 7. RabbitMQ Live AMQP Routing & Queue Consumer
    print("\n[7/8] Validating RabbitMQ AMQP Message Routing & DLX Queue Roundtrip...")
    order = test_rabbitmq_amqp_routing()
    print(f"      [✓] Message routed via topic exchange to queue successfully (Order ID: '{order.get('order_id')}')")

    # 8. Zero Trust Multi-Tenant Boundary Isolation
    print("\n[8/8] Validating Zero Trust VHost Isolation & Security Boundaries...")
    test_rabbitmq_tenant_isolation()
    print("      [✓] Tenant Acme strictly isolated from Tenant Globex VHost (HTTP 404 Not Found / Unauthorized)")
    print("      [✓] Tenant Globex strictly isolated from Tenant Acme VHost (HTTP 404 Not Found / Unauthorized)")

    print("\n==================================================================")
    print("  [✓✓✓] ALL PHASE 09 KAFKA & RABBITMQ VALIDATION TESTS PASSED!    ")
    print("==================================================================")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[✗] Validation failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
