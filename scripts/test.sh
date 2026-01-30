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

ensure_test_deps() {
  if "$PY" - <<'PY' >/dev/null 2>&1
import fastapi  # noqa: F401
import httpx  # noqa: F401
import pytest  # noqa: F401
import jsonschema  # noqa: F401
PY
  then
    return 0
  fi

  printf "[test] installing test dependencies via ./.venv/bin/pip install -e \".[test]\"...\n"
  if ! "$ROOT_DIR/.venv/bin/pip" install -e ".[test]"; then
    printf "[test] dependency install failed. Ensure network access and try again.\n"
    exit 1
  fi
}

ensure_test_deps

if [ ! -x "$ROOT_DIR/.venv/bin/pytest" ]; then
  printf "[test] pytest still missing after install. Aborting.\n"
  exit 1
fi

"$ROOT_DIR/.venv/bin/pytest"
