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

export PYTHONNOUSERSITE=1

"$PY" - <<'PY'
from alembic.config import Config
from alembic.script import ScriptDirectory

cfg = Config("alembic.ini")
script = ScriptDirectory.from_config(cfg)
heads = script.get_heads()
if len(heads) != 1:
    raise SystemExit(f"Expected exactly 1 Alembic head, found {len(heads)}: {heads}")
print(f"Alembic head OK: {heads[0]}")
PY
