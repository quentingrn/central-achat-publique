#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$ROOT_DIR"

PY="$ROOT_DIR/.venv/bin/python"
if [ ! -x "$PY" ]; then
  printf "[ci] missing .venv. Run: python3 -m venv .venv\n"
  exit 1
fi
if ! PY_CHECK=$("$PY" - <<'PY'
import sys
bad_markers = (".platformio", "conda")
paths = [sys.executable, sys.prefix, getattr(sys, "base_prefix", "")]
for path in paths:
    for marker in bad_markers:
        if marker in path:
            print(f"venv is based on an external env: {path}")
            raise SystemExit(1)
PY
); then
  printf "[ci] %s\n" "$PY_CHECK"
  exit 1
fi

export DATABASE_URL=${DATABASE_URL:-postgresql+psycopg://postgres:postgres@localhost:5432/central_achat_publique}
export PYTHONPATH="$ROOT_DIR"
export PYTHONNOUSERSITE=1

docker compose up -d postgres

until docker compose exec -T postgres pg_isready -U postgres >/dev/null 2>&1; do
  sleep 1
  echo "Waiting for postgres..."
done

./scripts/db_migrate.sh
"$PY" -m pytest
