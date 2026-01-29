#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$ROOT_DIR"

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "Not a git repository."
  exit 1
fi

if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
  echo "No commits yet; immutability check skipped."
  exit 0
fi

check_diff() {
  local diff_output
  diff_output=$(git diff --name-status "$@" -- alembic/versions || true)
  if [ -z "$diff_output" ]; then
    return 0
  fi

  while IFS= read -r line; do
    status=${line%%\t*}
    case "$status" in
      A)
        ;;
      *)
        echo "Immutable migrations violated: $line"
        exit 1
        ;;
    esac
  done <<< "$diff_output"
}

check_diff HEAD
check_diff --cached HEAD

echo "Alembic migrations immutability OK."
