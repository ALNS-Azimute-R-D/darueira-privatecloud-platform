#!/usr/bin/env python3
"""
==============================================================================
Script: scripts/bootstrap_food_market_data.py
Purpose: Idempotent data-plane bootstrap for the food-market services of tenant swfabrik-europe.
           1. Tenant PostgreSQL: role `food_market_app` (no superuser) and, in database `drr_tnt_bizapps_db`,
              the schemas schm01..schm06 owned by it, each with the table `tb_food_trading`
              (the columns the six services read and write).
           2. RabbitMQ (corpshared): user `food_market` with permissions on vhost `/`.
           3. Secrets in the tenant namespace (never committed): `food-market-db` and `food-market-mq`,
              read by the Helm charts with secretKeyRef. An existing secret keeps its password.
Usage:   python3 scripts/bootstrap_food_market_data.py
Env:     KUBECTL (default "microk8s kubectl"), TENANT_NS (drr-tnt-swfabrik-europe-dev)
==============================================================================
"""

import base64
import json
import os
import secrets
import shlex
import subprocess
import sys

KUBECTL = shlex.split(os.environ.get("KUBECTL", "microk8s kubectl"))
TENANT_NS = os.environ.get("TENANT_NS", "drr-tnt-swfabrik-europe-dev")
PLAT_NS = "drr-corpshared-plat"
DB = "drr_tnt_bizapps_db"
DB_ROLE = "food_market_app"
MQ_USER = "food_market"
SCHEMAS = [f"schm{n:02d}" for n in range(1, 7)]


def kube(*args, ns=None, stdin=None, check=True):
    cmd = [*KUBECTL, *(["-n", ns] if ns else []), *args]
    res = subprocess.run(cmd, input=stdin, capture_output=True, text=True)
    if check and res.returncode != 0:
        sys.exit(f"[ERROR] {' '.join(cmd[len(KUBECTL):][:4])}...: {res.stderr.strip()[:400]}")
    return res


def existing_secret(name, key):
    res = kube("get", "secret", name, "-o", "json", ns=TENANT_NS, check=False)
    if res.returncode != 0:
        return None
    data = json.loads(res.stdout).get("data", {})
    return base64.b64decode(data[key]).decode() if key in data else None


def apply_secret(name, values):
    manifest = {
        "apiVersion": "v1", "kind": "Secret", "type": "Opaque",
        "metadata": {"name": name, "namespace": TENANT_NS,
                     "labels": {"darueira.io/tenant": "swfabrik-europe", "darueira.io/project": "food-market",
                                "app.kubernetes.io/managed-by": "bootstrap_food_market_data"}},
        "stringData": values,
    }
    kube("apply", "-f", "-", stdin=json.dumps(manifest))


def postgres():
    print("--> 1. Tenant PostgreSQL (role, schemas, tb_food_trading)")
    password = existing_secret("food-market-db", "password") or secrets.token_urlsafe(24).replace("-", "x").replace("_", "y")
    psql = "export PGPASSWORD=$POSTGRES_PASSWORD; psql -v ON_ERROR_STOP=1 -q -U $POSTGRES_USER -d "

    role_sql = f"""
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{DB_ROLE}') THEN
    CREATE ROLE {DB_ROLE} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '{password}';
  ELSE
    ALTER ROLE {DB_ROLE} LOGIN PASSWORD '{password}';
  END IF;
END $$;
GRANT CONNECT ON DATABASE {DB} TO {DB_ROLE};
"""
    kube("exec", "-i", "tenant-postgres-0", "--", "sh", "-c", psql + "postgres", ns=TENANT_NS, stdin=role_sql)

    ddl = []
    for schema in SCHEMAS:
        ddl.append(f"""
CREATE SCHEMA IF NOT EXISTS {schema} AUTHORIZATION {DB_ROLE};
CREATE TABLE IF NOT EXISTS {schema}.tb_food_trading (
  id          BIGSERIAL PRIMARY KEY,
  trading_id  VARCHAR(64)    NOT NULL UNIQUE,
  market_id   VARCHAR(64)    NOT NULL,
  item_name   VARCHAR(128)   NOT NULL,
  quantity    NUMERIC(12, 2) NOT NULL,
  unit_price  NUMERIC(12, 2) NOT NULL,
  total_price NUMERIC(12, 2) NOT NULL,
  trader_name VARCHAR(128)   NOT NULL,
  status      VARCHAR(32)    NOT NULL,
  created_at  TIMESTAMPTZ    NOT NULL
);
ALTER TABLE {schema}.tb_food_trading OWNER TO {DB_ROLE};
ALTER SEQUENCE IF EXISTS {schema}.tb_food_trading_id_seq OWNER TO {DB_ROLE};
""")
    kube("exec", "-i", "tenant-postgres-0", "--", "sh", "-c", psql + DB, ns=TENANT_NS, stdin="".join(ddl))
    print(f"    [✓] role {DB_ROLE}; schemas {SCHEMAS[0]}..{SCHEMAS[-1]} with tb_food_trading")

    apply_secret("food-market-db", {
        "username": DB_ROLE, "password": password, "host": f"tenant-postgres.{TENANT_NS}.svc.cluster.local",
        "port": "5432", "database": DB,
    })
    print("    [✓] secret food-market-db")


def rabbitmq():
    print("--> 2. RabbitMQ user and permissions")
    password = existing_secret("food-market-mq", "password") or secrets.token_urlsafe(24).replace("-", "x").replace("_", "y")
    pod = kube("get", "pod", "-l", "app.kubernetes.io/name=message-broker-rabbitmq", "-o", "name", ns=PLAT_NS).stdout.split()[0]
    users = kube("exec", pod, "--", "rabbitmqctl", "list_users", "--silent", ns=PLAT_NS).stdout
    verb = "change_password" if MQ_USER in users else "add_user"
    kube("exec", pod, "--", "rabbitmqctl", verb, MQ_USER, password, ns=PLAT_NS)
    kube("exec", pod, "--", "rabbitmqctl", "set_permissions", "-p", "/", MQ_USER, ".*", ".*", ".*", ns=PLAT_NS)
    print(f"    [✓] user {MQ_USER} ({'password refreshed' if verb == 'change_password' else 'created'})")
    apply_secret("food-market-mq", {
        "username": MQ_USER, "password": password, "host": f"message-broker-rabbitmq.{PLAT_NS}.svc.cluster.local",
        "port": "5672", "vhost": "/",
    })
    print("    [✓] secret food-market-mq")


if __name__ == "__main__":
    postgres()
    rabbitmq()
    print("Done. The charts read food-market-db and food-market-mq from namespace", TENANT_NS)
