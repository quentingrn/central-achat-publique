#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT_DIR"

export PYTHONPATH="$ROOT_DIR"

if command -v docker >/dev/null 2>&1; then
  docker compose up -d postgres
fi

./scripts/db_migrate.sh
exec python -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
