#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT_DIR"

: "${DATABASE_URL:=postgresql+psycopg://postgres:postgres@localhost:5432/central_achat_publique}"
export DATABASE_URL
export PYTHONPATH="$ROOT_DIR"

python -m pytest
