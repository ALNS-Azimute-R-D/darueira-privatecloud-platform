#!/usr/bin/env python3
"""
==============================================================================
Darueira Private Cloud Platform - Enterprise Message Brokers & Multi-Tenancy
Declarative Kafka/Redpanda & RabbitMQ 4 Topology Bootstrapper
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

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "message-broker-rabbitmq.drr-corpshared-plat.svc.cluster.local:15672")
RABBITMQ_ADDR = f"http://{RABBITMQ_HOST}"
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "drr_admin")
RABBITMQ_PASS = os.environ.get("RABBITMQ_PASS", "darueira-admin123")
ADMIN_AUTH = "Basic " + base64.b64encode(f"{RABBITMQ_USER}:{RABBITMQ_PASS}".encode("utf-8")).decode("utf-8")

KAFKA_POD = os.environ.get("KAFKA_POD", "deploy/message-broker-kafka")
KAFKA_NS = os.environ.get("KAFKA_NS", "drr-corpshared-plat")

KAFKA_TOPICS = [
    {"name": "drr.authz.tuple-events", "partitions": 3, "replicas": 1},
    {"name": "drr.tenant.lifecycle-events", "partitions": 3, "replicas": 1},
    {"name": "drr.environment.events", "partitions": 3, "replicas": 1},
    {"name": "drr.audit.log-events", "partitions": 3, "replicas": 1},
    {"name": "acme.storefront.orders", "partitions": 2, "replicas": 1},
    {"name": "acme.logistics.tracking", "partitions": 2, "replicas": 1},
    {"name": "globex.security.findings", "partitions": 2, "replicas": 1}
]

RABBITMQ_VHOSTS = ["drr-platform", "acme", "globex"]

RABBITMQ_USERS = [
    {"username": "platform_worker", "password": "worker_secure_pass_2026", "tags": "management", "vhost": "drr-platform"},
    {"username": "acme_user", "password": "acme_secure_pass_2026", "tags": "management", "vhost": "acme"},
    {"username": "globex_user", "password": "globex_secure_pass_2026", "tags": "management", "vhost": "globex"}
]

RABBITMQ_TOPOLOGY = [
    # Platform VHost
    {
        "vhost": "drr-platform",
        "exchanges": [{"name": "platform.events.topic", "type": "topic"}],
        "queues": [{"name": "platform.audit.queue"}, {"name": "platform.telemetry.queue"}],
        "bindings": [
            {"exchange": "platform.events.topic", "queue": "platform.audit.queue", "routing_key": "audit.#"},
            {"exchange": "platform.events.topic", "queue": "platform.telemetry.queue", "routing_key": "telemetry.#"}
        ]
    },
    # Acme VHost
    {
        "vhost": "acme",
        "exchanges": [
            {"name": "acme.orders.topic", "type": "topic"},
            {"name": "acme.deadletter.direct", "type": "direct"}
        ],
        "queues": [
            {"name": "acme.orders.processing", "arguments": {"x-dead-letter-exchange": "acme.deadletter.direct", "x-dead-letter-routing-key": "deadletter"}},
            {"name": "acme.orders.deadletter"},
            {"name": "acme.notifications.queue"}
        ],
        "bindings": [
            {"exchange": "acme.orders.topic", "queue": "acme.orders.processing", "routing_key": "order.#"},
            {"exchange": "acme.orders.topic", "queue": "acme.notifications.queue", "routing_key": "notification.#"},
            {"exchange": "acme.deadletter.direct", "queue": "acme.orders.deadletter", "routing_key": "deadletter"}
        ]
    },
    # Globex VHost
    {
        "vhost": "globex",
        "exchanges": [{"name": "globex.audit.topic", "type": "topic"}],
        "queues": [{"name": "globex.audit.processing"}, {"name": "globex.reports.queue"}],
        "bindings": [
            {"exchange": "globex.audit.topic", "queue": "globex.audit.processing", "routing_key": "audit.#"},
            {"exchange": "globex.audit.topic", "queue": "globex.reports.queue", "routing_key": "report.#"}
        ]
    }
]


def rmq_request(path, data=None, method="GET", auth=ADMIN_AUTH):
    clean_path = path.lstrip("/")
    url = f"{RABBITMQ_ADDR}/api/{clean_path}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    headers = {
        "Authorization": auth,
        "Content-Type": "application/json"
    }
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 204 or resp.length == 0:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        if e.code == 400 and "already exists" in err_msg:
            return None
        if e.code == 400 and "inequivalent arg" in err_msg and method == "PUT" and "queues/" in clean_path:
            del_req = urllib.request.Request(url, headers={"Authorization": auth}, method="DELETE")
            with urllib.request.urlopen(del_req, timeout=15):
                pass
            retry_req = urllib.request.Request(url, data=body, headers=headers, method=method)
            with urllib.request.urlopen(retry_req, timeout=15) as retry_resp:
                if retry_resp.status == 204 or retry_resp.length == 0:
                    return None
                return json.loads(retry_resp.read().decode("utf-8"))
        print(f"    [!] RabbitMQ HTTP {e.code} on {path}: {err_msg}")
        raise


def bootstrap_kafka():
    print("--> Bootstrapping Kafka/Redpanda Event Streaming Topics...")
    # List existing topics
    show_cmd = f"microk8s kubectl exec -n {KAFKA_NS} {KAFKA_POD} -c redpanda -- rpk topic list"
    try:
        proc = subprocess.run(show_cmd, shell=True, capture_output=True, text=True, check=True)
        existing_topics = proc.stdout
    except Exception as e:
        print(f"    Notice listing Kafka topics: {e}")
        existing_topics = ""

    for item in KAFKA_TOPICS:
        t_name = item["name"]
        if t_name not in existing_topics:
            create_cmd = f"microk8s kubectl exec -n {KAFKA_NS} {KAFKA_POD} -c redpanda -- rpk topic create {t_name} -p {item['partitions']} -r {item['replicas']}"
            res = subprocess.run(create_cmd, shell=True, capture_output=True, text=True)
            if res.returncode == 0:
                print(f"    [✓] Created Kafka topic: {t_name} (Partitions: {item['partitions']}, Replicas: {item['replicas']})")
            else:
                print(f"    [!] Topic create note for {t_name}: {res.stderr.strip()}")
        else:
            print(f"    [✓] Kafka topic already exists: {t_name}")


def bootstrap_rabbitmq():
    print("--> Bootstrapping RabbitMQ 4 Virtual Hosts, Users, and Multi-Tenant Topology...")

    # 1. Create Virtual Hosts
    for vh in RABBITMQ_VHOSTS:
        vh_enc = urllib.parse.quote(vh, safe="")
        rmq_request(f"vhosts/{vh_enc}", method="PUT")
        print(f"    [✓] Created RabbitMQ Virtual Host: /{vh}")

    # 2. Create Users & Assign VHost Permissions
    for u in RABBITMQ_USERS:
        uname = u["username"]
        upass = u["password"]
        utags = u["tags"]
        uvhost = u["vhost"]

        # Create/update user
        rmq_request(f"users/{uname}", data={"password": upass, "tags": utags}, method="PUT")

        # Set strict permissions on assigned vhost only
        vh_enc = urllib.parse.quote(uvhost, safe="")
        rmq_request(f"permissions/{vh_enc}/{uname}", data={"configure": ".*", "write": ".*", "read": ".*"}, method="PUT")

        # Also ensure admin has full permissions on this vhost
        rmq_request(f"permissions/{vh_enc}/{RABBITMQ_USER}", data={"configure": ".*", "write": ".*", "read": ".*"}, method="PUT")

        print(f"    [✓] Configured user '{uname}' strictly scoped to VHost '/{uvhost}'")

    # 3. Provision Exchanges, Queues, and Bindings per VHost
    for topo in RABBITMQ_TOPOLOGY:
        vh = topo["vhost"]
        vh_enc = urllib.parse.quote(vh, safe="")

        # Exchanges
        for ex in topo.get("exchanges", []):
            ex_name = ex["name"]
            ex_type = ex["type"]
            rmq_request(f"exchanges/{vh_enc}/{ex_name}", data={"type": ex_type, "durable": True}, method="PUT")
            print(f"    [✓] VHost '/{vh}' -> Created Exchange: {ex_name} (Type: {ex_type})")

        # Queues
        for q in topo.get("queues", []):
            q_name = q["name"]
            q_args = q.get("arguments", {})
            rmq_request(f"queues/{vh_enc}/{q_name}", data={"durable": True, "arguments": q_args}, method="PUT")
            print(f"    [✓] VHost '/{vh}' -> Created Queue: {q_name}")

        # Bindings
        for b in topo.get("bindings", []):
            ex_name = b["exchange"]
            q_name = b["queue"]
            r_key = b["routing_key"]
            rmq_request(f"bindings/{vh_enc}/e/{ex_name}/q/{q_name}", data={"routing_key": r_key}, method="POST")
            print(f"    [✓] VHost '/{vh}' -> Bound {ex_name} -> {q_name} (Routing Key: '{r_key}')")


def main():
    print("==================================================================")
    print("  Phase 09: Bootstrapping Kafka & RabbitMQ 4 Message Brokers      ")
    print("==================================================================")

    # 1. Healthcheck RabbitMQ
    for _ in range(10):
        try:
            with urllib.request.urlopen(f"{RABBITMQ_ADDR}/api/overview", timeout=3) as resp:
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(2)

    # 2. Bootstrap Kafka Topics
    bootstrap_kafka()

    # 3. Bootstrap RabbitMQ VHosts & Topology
    bootstrap_rabbitmq()

    print("\n[✓] Message Brokers & Multi-Tenant topology bootstrapping completed successfully!")


if __name__ == "__main__":
    main()
