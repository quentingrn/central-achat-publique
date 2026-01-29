#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT_DIR"

PY="$ROOT_DIR/.venv/bin/python"
if [ ! -x "$PY" ]; then
  printf "[test] missing .venv. Run: python3 -m venv .venv\n"
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
  printf "[test] %s\n" "$PY_CHECK"
  exit 1
fi

: "${DATABASE_URL:=postgresql+psycopg://postgres:postgres@localhost:5432/central_achat_publique}"
export DATABASE_URL
export PYTHONPATH="$ROOT_DIR"
export PYTHONNOUSERSITE=1

if [ ! -x "$ROOT_DIR/.venv/bin/pytest" ]; then
  printf "[test] pytest not found in .venv. Run: ./.venv/bin/pip install -e \".[test]\"\n"
  exit 1
fi

"$ROOT_DIR/.venv/bin/pytest"
