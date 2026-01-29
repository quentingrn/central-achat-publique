#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$ROOT_DIR"

python - <<'PY'
from alembic.config import Config
from alembic.script import ScriptDirectory

cfg = Config("alembic.ini")
script = ScriptDirectory.from_config(cfg)
heads = script.get_heads()
if len(heads) != 1:
    raise SystemExit(f"Expected exactly 1 Alembic head, found {len(heads)}: {heads}")
print(f"Alembic head OK: {heads[0]}")
PY
