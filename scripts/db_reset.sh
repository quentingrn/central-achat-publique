#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT_DIR"

: "${DATABASE_URL:=postgresql+psycopg://postgres:postgres@localhost:5432/central_achat_publique}"
export DATABASE_URL

psql "$DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL'
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO public;
SQL

./scripts/db_migrate.sh
