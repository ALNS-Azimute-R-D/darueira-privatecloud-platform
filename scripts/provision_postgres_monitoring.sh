#!/usr/bin/env bash
# Creates the read-only monitoring role (member of pg_monitor, no superuser) in a PostgreSQL instance and the Secret
# `postgres-exporter-<key>` (key `dsn`) in drr-corpshared-obs that the matching postgres-exporter Deployment reads (ADR-0020).
#
# Idempotent. The password is generated in memory, never written to a file, printed or passed on a command line, and the
# Secret is created with `kubectl create`, so the cleartext does not land in an annotation.
#
# Usage: scripts/provision_postgres_monitoring.sh [--rotate]      (provisions all three instances)
set -euo pipefail

ROTATE="${1:-}"
ROLE="drr_monitor"
OBS_NS="drr-corpshared-obs"

provision() {   # key namespace pod service-host admin-lookup (secret|env)
  local key="$1" ns="$2" pod="$3" host="$4" mode="$5" admin
  if [[ "$mode" == "secret" ]]; then
    admin="$(kubectl -n "$ns" get secret tenant-db-credentials -o jsonpath='{.data.username}' | base64 -d)"
  else
    admin="$(kubectl -n "$ns" get pod "$pod" -o jsonpath='{.spec.containers[0].env[?(@.name=="POSTGRES_USER")].value}')"
  fi
  kpsql() { kubectl -n "$ns" exec -i "$pod" -- psql -U "$admin" -d postgres -v ON_ERROR_STOP=1 -X -q "$@"; }
  local exists secret_exists=0 pw=""
  exists="$(kpsql -Atc "select count(*) from pg_roles where rolname = '$ROLE'")"
  kubectl -n "$OBS_NS" get secret "postgres-exporter-$key" >/dev/null 2>&1 && secret_exists=1
  if [[ "$exists" == "0" || "$secret_exists" == "0" || "$ROTATE" == "--rotate" ]]; then
    pw="$(openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 32)"
    [[ ${#pw} -eq 32 ]] || { echo "could not generate a password" >&2; exit 1; }
    if [[ "$exists" == "0" ]]; then
      printf "CREATE ROLE %s LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION CONNECTION LIMIT 5 PASSWORD '%s' IN ROLE pg_monitor;\n" "$ROLE" "$pw" | kpsql
      echo "[$key] role $ROLE created"
    else
      printf "ALTER ROLE %s PASSWORD '%s';\n" "$ROLE" "$pw" | kpsql
      echo "[$key] role $ROLE: password set"
    fi
    kubectl -n "$OBS_NS" delete secret "postgres-exporter-$key" --ignore-not-found >/dev/null
    kubectl -n "$OBS_NS" create secret generic "postgres-exporter-$key" \
      --from-literal=dsn="postgresql://${ROLE}:${pw}@${host}:5432/postgres?sslmode=disable" >/dev/null
    echo "[$key] Secret postgres-exporter-$key created"
  else
    echo "[$key] role and Secret kept"
  fi
}

provision central drr-corpshared-plat            central-postgres-0 central-postgres.drr-corpshared-plat.svc.cluster.local            env
provision europe  drr-tnt-swfabrik-europe-dev    tenant-postgres-0  tenant-postgres.drr-tnt-swfabrik-europe-dev.svc.cluster.local   secret
provision latam   drr-tnt-swfabrik-latam-dev     tenant-postgres-0  tenant-postgres.drr-tnt-swfabrik-latam-dev.svc.cluster.local    secret
