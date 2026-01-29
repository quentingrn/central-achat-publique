#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$ROOT_DIR"

export DATABASE_URL=${DATABASE_URL:-postgresql+psycopg://postgres:postgres@localhost:5432/central_achat_publique}
export PYTHONPATH="$ROOT_DIR"

docker compose up -d postgres

until docker compose exec -T postgres pg_isready -U postgres >/dev/null 2>&1; do
  sleep 1
  echo "Waiting for postgres..."
done

./scripts/db_migrate.sh
python -m pytest
