#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT_DIR"

PY="$ROOT_DIR/.venv/bin/python"
if [ ! -x "$PY" ]; then
  printf "[db] missing .venv. Run: python3 -m venv .venv\n"
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
  printf "[db] %s\n" "$PY_CHECK"
  exit 1
fi

export PYTHONPATH="$ROOT_DIR"
export PYTHONNOUSERSITE=1

"$ROOT_DIR/.venv/bin/alembic" -c alembic.ini upgrade head
