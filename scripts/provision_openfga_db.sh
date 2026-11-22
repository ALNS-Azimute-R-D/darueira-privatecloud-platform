#!/usr/bin/env bash
# Provisions the PostgreSQL database, the least-privilege role and the Secret that OpenFGA needs to persist its stores,
# models and tuples (ADR-0021). The datastore is the control-plane PostgreSQL (central-postgres).
#
# Idempotent: existing objects are kept. The password is generated in memory, never written to a file, never printed, never
# passed on a command line; the Secret is created (not applied) so the cleartext stays out of last-applied annotations.
#
# Usage: scripts/provision_openfga_db.sh [--rotate]   (--rotate: new password; OpenFGA must restart afterwards)
set -euo pipefail

ROTATE="${1:-}"
NS="${NS:-drr-corpshared-plat}"
POD="${POD:-central-postgres-0}"
DB="${DB:-drr_openfga_db}"
ROLE="${ROLE:-openfga_app}"
SECRET="${SECRET:-openfga-db}"
HOST="central-postgres.${NS}.svc.cluster.local"

ADMIN="$(kubectl -n "$NS" get pod "$POD" -o jsonpath='{.spec.containers[0].env[?(@.name=="POSTGRES_USER")].value}')"
[[ -n "$ADMIN" ]] || { echo "could not find the PostgreSQL admin user on $POD" >&2; exit 1; }
kpsql() { kubectl -n "$NS" exec -i "$POD" -- psql -U "$ADMIN" -v ON_ERROR_STOP=1 -X -q "$@"; }
scalar() { kpsql -d postgres -Atc "$1"; }
secret_exists() { kubectl -n "$NS" get secret "$1" >/dev/null 2>&1; }

role_exists="$(scalar "select count(*) from pg_roles where rolname = '$ROLE'")"
db_exists="$(scalar "select count(*) from pg_database where datname = '$DB'")"

PASSWORD=""
if [[ "$role_exists" == "0" || "$ROTATE" == "--rotate" ]] || ! secret_exists "$SECRET"; then
  PASSWORD="$(openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 32)"
  [[ ${#PASSWORD} -eq 32 ]] || { echo "could not generate a password" >&2; exit 1; }
  if [[ "$role_exists" == "0" ]]; then
    printf "CREATE ROLE %s LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION CONNECTION LIMIT 30 PASSWORD '%s';\n" "$ROLE" "$PASSWORD" | kpsql -d postgres
    echo "role $ROLE created"
  else
    printf "ALTER ROLE %s PASSWORD '%s';\n" "$ROLE" "$PASSWORD" | kpsql -d postgres
    echo "role $ROLE: password set"
  fi
else
  echo "role $ROLE kept"
fi

if [[ "$db_exists" == "0" ]]; then
  printf 'CREATE DATABASE "%s" OWNER %s;\n' "$DB" "$ROLE" | kpsql -d postgres
  echo "database $DB created"
else
  echo "database $DB kept"
fi
kpsql -d postgres <<SQL
REVOKE ALL ON DATABASE "$DB" FROM PUBLIC;
GRANT CONNECT ON DATABASE "$DB" TO $ROLE;
SQL
kpsql -d "$DB" <<SQL
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO $ROLE;
SQL

if [[ -n "$PASSWORD" ]]; then
  secret_exists "$SECRET" && kubectl -n "$NS" delete secret "$SECRET" >/dev/null
  kubectl -n "$NS" create secret generic "$SECRET" \
    --from-file=uri=<(printf 'postgres://%s:%s@%s:5432/%s?sslmode=disable' "$ROLE" "$PASSWORD" "$HOST" "$DB") >/dev/null
  kubectl -n "$NS" label secret "$SECRET" app.kubernetes.io/name=openfga darueira.io/tier=enterprise-shared --overwrite >/dev/null
  echo "secret $SECRET written"
else
  echo "secret $SECRET kept"
fi
