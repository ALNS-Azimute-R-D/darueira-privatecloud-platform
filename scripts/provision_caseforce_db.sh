#!/usr/bin/env bash
# Provisions the PostgreSQL database, the least-privilege role and the Secret that the CaseForce LegalHub backend
# needs (ADR-0018: tenant relational data lives on tenant-postgres, tenant-mysql is decommissioned; tenant-postgres is
# PaaS, ADR-0016).
#
# The role owns the database because the backend runs its Flyway migrations at startup. It is not a superuser, cannot
# create databases or roles, and nobody else can connect to the database.
#
# Idempotent: existing objects are kept. The password is generated in memory, never written to a file, never printed,
# never passed on a command line. The Secret is created with `kubectl create` (not `apply`), so the cleartext does not
# land in the last-applied-configuration annotation.
#
# Usage: scripts/provision_caseforce_db.sh [--rotate]
#   --rotate   generate a new password even if the role and the Secret exist (the backend must restart afterwards).
set -euo pipefail

ROTATE="${1:-}"
NS="${NS:-drr-tnt-swfabrik-europe-dev}"
POD="${POD:-tenant-postgres-0}"
DB="${DB:-drr_tnt_caseforce_db}"
ROLE="${ROLE:-caseforce_app}"
OWNER_SECRET="${OWNER_SECRET:-tenant-db-credentials}"
DB_SECRET="${DB_SECRET:-caseforce-db}"
HOST="tenant-postgres.${NS}.svc.cluster.local"

[[ "$ROLE" =~ ^[a-z_][a-z0-9_]*$ ]] || { echo "ROLE must be a lower case identifier" >&2; exit 2; }
[[ "$DB" =~ ^[a-z_][a-z0-9_]*$ ]] || { echo "DB must be a lower case identifier" >&2; exit 2; }

ADMIN="$(kubectl -n "$NS" get secret "$OWNER_SECRET" -o jsonpath='{.data.username}' | base64 -d)"
kpsql() { kubectl -n "$NS" exec -i "$POD" -- psql -U "$ADMIN" -v ON_ERROR_STOP=1 -X -q "$@"; }
scalar() { kpsql -d postgres -Atc "$1"; }
secret_exists() { kubectl -n "$NS" get secret "$1" >/dev/null 2>&1; }

role_exists="$(scalar "select count(*) from pg_roles where rolname = '$ROLE'")"
db_exists="$(scalar "select count(*) from pg_database where datname = '$DB'")"

# 1. Role and password (the password only ever lives in this shell variable).
PASSWORD=""
need_password=0
secret_exists "$DB_SECRET" || need_password=1
if [[ "$role_exists" == "0" || "$ROTATE" == "--rotate" || "$need_password" == "1" ]]; then
  PASSWORD="$(openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 32)"
  [[ ${#PASSWORD} -eq 32 ]] || { echo "could not generate a password" >&2; exit 1; }
  if [[ "$role_exists" == "0" ]]; then
    printf "CREATE ROLE %s LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION CONNECTION LIMIT 20 PASSWORD '%s';\n" "$ROLE" "$PASSWORD" | kpsql -d postgres
    echo "role $ROLE created"
  else
    printf "ALTER ROLE %s PASSWORD '%s';\n" "$ROLE" "$PASSWORD" | kpsql -d postgres
    echo "role $ROLE: password rotated"
  fi
else
  echo "role $ROLE kept"
fi

# 2. Database owned by the application role (Flyway needs DDL), closed to everybody else.
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

# 3. Secret. Created, never applied; the values come from process substitution, not from arguments.
if [[ -n "$PASSWORD" ]]; then
  secret_exists "$DB_SECRET" && kubectl -n "$NS" delete secret "$DB_SECRET" >/dev/null
  kubectl -n "$NS" create secret generic "$DB_SECRET" \
    --from-file=host=<(printf '%s' "$HOST") \
    --from-file=port=<(printf '5432') \
    --from-file=database=<(printf '%s' "$DB") \
    --from-file=username=<(printf '%s' "$ROLE") \
    --from-file=password=<(printf '%s' "$PASSWORD") >/dev/null
  kubectl -n "$NS" label secret "$DB_SECRET" darueira.io/project=legaltech-caseforce darueira.io/tenant=swfabrik-europe darueira.io/tier=tenant-workload --overwrite >/dev/null
  echo "secret $DB_SECRET written"
else
  echo "secret $DB_SECRET kept"
fi

# 4. Verification as the application role over TCP (scram), without writing any row.
APP_PASSWORD="$(kubectl -n "$NS" get secret "$DB_SECRET" -o jsonpath='{.data.password}' | base64 -d)"
as_app() { { printf '%s\n' "$APP_PASSWORD"; cat; } | kubectl -n "$NS" exec -i "$POD" -- sh -c "IFS= read -r PGPASSWORD; export PGPASSWORD; exec psql -h 127.0.0.1 -U $ROLE -d '$DB' -X -q -At -v ON_ERROR_STOP=1"; }
echo "--- verification as $ROLE"
as_app <<SQL
select 'login ok, database=' || current_database();
select 'superuser=' || rolsuper || ' createdb=' || rolcreatedb || ' createrole=' || rolcreaterole from pg_roles where rolname = current_user;
select 'create_in_public=' || has_schema_privilege('public','CREATE');
SQL
