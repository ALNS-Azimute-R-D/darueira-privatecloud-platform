#!/usr/bin/env bash
# Provisions the database, the least-privilege role, the table and the two Secrets that the voize EHR integrator needs
# to share its Vivendi session between replicas (voize spec 006, ADR 0018; tenant-postgres is PaaS, ADR-0016).
#
# Idempotent: existing objects are kept. Passwords and the encryption key are generated in memory, never written to a
# file, never printed, and never passed on a command line. Secrets are created with `kubectl create` (not `apply`), so the
# cleartext does not land in the last-applied-configuration annotation.
#
# Usage: scripts/provision_voize_session_db.sh <path to voize db/sql/V1__tb_shared_auth_session.sql> [--rotate]
#   --rotate   generate a new password and a new key even if the objects exist (stored sessions become unreadable and
#              are replaced at the next login).
set -euo pipefail

DDL_FILE="${1:?usage: $0 <path to V1__tb_shared_auth_session.sql> [--rotate]}"
ROTATE="${2:-}"
NS="${NS:-drr-tnt-swfabrik-europe-dev}"
POD="${POD:-tenant-postgres-0}"
DB="${DB:-DBVoizeEHRIntegrator}"
ROLE="${ROLE:-dbavoize01}"
OWNER_SECRET="${OWNER_SECRET:-tenant-db-credentials}"
DB_SECRET="${DB_SECRET:-alns-voize-ehr-integrator-db}"
SESSION_SECRET="${SESSION_SECRET:-alns-voize-ehr-integrator-session}"
HOST="tenant-postgres.${NS}.svc.cluster.local"

[[ -f "$DDL_FILE" ]] || { echo "DDL file not found: $DDL_FILE" >&2; exit 2; }
[[ "$ROLE" =~ ^[a-z_][a-z0-9_]*$ ]] || { echo "ROLE must be a lower case identifier" >&2; exit 2; }

ADMIN="$(kubectl -n "$NS" get secret "$OWNER_SECRET" -o jsonpath='{.data.username}' | base64 -d)"
kpsql() { kubectl -n "$NS" exec -i "$POD" -- psql -U "$ADMIN" -v ON_ERROR_STOP=1 -X -q "$@"; }
scalar() { kpsql -d postgres -Atc "$1"; }
secret_exists() { kubectl -n "$NS" get secret "$1" >/dev/null 2>&1; }
labels() { kubectl -n "$NS" label secret "$1" darueira.io/project=ehr-integrations darueira.io/tenant=swfabrik-europe --overwrite >/dev/null; }

role_exists="$(scalar "select count(*) from pg_roles where rolname = '$ROLE'")"
db_exists="$(scalar "select count(*) from pg_database where datname = '$DB'")"

# 1-2. Role and password (the password only ever lives in this shell variable).
PASSWORD=""
need_password=0
secret_exists "$DB_SECRET" || need_password=1
if [[ "$role_exists" == "0" || "$ROTATE" == "--rotate" || "$need_password" == "1" ]]; then
  PASSWORD="$(openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 32)"
  [[ ${#PASSWORD} -eq 32 ]] || { echo "could not generate a password" >&2; exit 1; }
  if [[ "$role_exists" == "0" ]]; then
    printf "CREATE ROLE %s LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION CONNECTION LIMIT 10 PASSWORD '%s';\n" "$ROLE" "$PASSWORD" | kpsql -d postgres
    echo "role $ROLE created"
  else
    printf "ALTER ROLE %s PASSWORD '%s';\n" "$ROLE" "$PASSWORD" | kpsql -d postgres
    echo "role $ROLE: password rotated"
  fi
else
  echo "role $ROLE kept"
fi

# 3. Database owned by the admin, so the application role cannot alter tables.
if [[ "$db_exists" == "0" ]]; then
  printf 'CREATE DATABASE "%s" OWNER %s;\n' "$DB" "$ADMIN" | kpsql -d postgres
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
GRANT USAGE ON SCHEMA public TO $ROLE;
SQL

# 4. Table (the DDL file of the voize repository) and the privileges of SHARE-11.
{ echo "SET search_path TO public;"; cat "$DDL_FILE"; } | kpsql -d "$DB"
kpsql -d "$DB" -c "GRANT SELECT, INSERT, UPDATE ON tb_shared_auth_session TO $ROLE;"
echo "table tb_shared_auth_session ready, SELECT/INSERT/UPDATE granted to $ROLE"

# 5. Secrets. Created, never applied; the values come from process substitution, not from arguments.
if [[ -n "$PASSWORD" ]]; then
  secret_exists "$DB_SECRET" && kubectl -n "$NS" delete secret "$DB_SECRET" >/dev/null
  kubectl -n "$NS" create secret generic "$DB_SECRET" \
    --from-file=url=<(printf 'jdbc:postgresql://%s:5432/%s' "$HOST" "$DB") \
    --from-file=user=<(printf '%s' "$ROLE") \
    --from-file=password=<(printf '%s' "$PASSWORD") >/dev/null
  labels "$DB_SECRET"
  echo "secret $DB_SECRET written"
else
  echo "secret $DB_SECRET kept"
fi
if [[ "$ROTATE" == "--rotate" ]] || ! secret_exists "$SESSION_SECRET"; then
  KEY="$(openssl rand -base64 32 | tr -d '\n')"
  secret_exists "$SESSION_SECRET" && kubectl -n "$NS" delete secret "$SESSION_SECRET" >/dev/null
  kubectl -n "$NS" create secret generic "$SESSION_SECRET" --from-file=session-store-key=<(printf '%s' "$KEY") >/dev/null
  labels "$SESSION_SECRET"
  echo "secret $SESSION_SECRET written"
else
  echo "secret $SESSION_SECRET kept"
fi

# 6. Verification as the application role over TCP (scram), without writing any row.
APP_PASSWORD="$(kubectl -n "$NS" get secret "$DB_SECRET" -o jsonpath='{.data.password}' | base64 -d)"
as_app() { { printf '%s\n' "$APP_PASSWORD"; cat; } | kubectl -n "$NS" exec -i "$POD" -- sh -c "IFS= read -r PGPASSWORD; export PGPASSWORD; exec psql -h 127.0.0.1 -U $ROLE -d '$DB' -X -q -At -v ON_ERROR_STOP=1"; }
echo "--- verification as $ROLE"
as_app <<'SQL'
select 'select='  || has_table_privilege('tb_shared_auth_session','SELECT');
select 'insert='  || has_table_privilege('tb_shared_auth_session','INSERT');
select 'update='  || has_table_privilege('tb_shared_auth_session','UPDATE');
select 'delete='  || has_table_privilege('tb_shared_auth_session','DELETE');
select 'create_in_public=' || has_schema_privilege('public','CREATE');
select 'rows=' || count(*) from tb_shared_auth_session;
SQL
if echo 'create table should_fail(i int);' | as_app >/dev/null 2>&1; then echo "UNEXPECTED: the role can create tables" >&2; exit 1; else echo "create table: denied (expected)"; fi
echo done
