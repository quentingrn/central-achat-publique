#!/usr/bin/env bash
set -euo pipefail

log() {
  printf "[start] %s\n" "$*"
}

log_ports() {
  printf "[ports] %s\n" "$*"
}

log_docker() {
  printf "[docker] %s\n" "$*"
}

log_brew() {
  printf "[brew] %s\n" "$*"
}

log_py() {
  printf "[py] %s\n" "$*"
}

log_deps() {
  printf "[deps] %s\n" "$*"
}

log_db() {
  printf "[db] %s\n" "$*"
}

assert_venv() {
  if [ ! -x ".venv/bin/python" ]; then
    log_py "missing .venv. Run: python3 -m venv .venv"
    exit 1
  fi
  local py_check
  if ! py_check=$(".venv/bin/python" - <<'PY'
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
    log_py "$py_check"
    log_py "recreate venv with system python3 to avoid leaks"
    exit 1
  fi
}

on_error() {
  local line="$1"
  local cmd="$2"
  log "error on line ${line}: ${cmd}"
  log "hint: check docker status, ports, and venv dependencies"
}

trap 'on_error $LINENO "$BASH_COMMAND"' ERR

if command -v git >/dev/null 2>&1; then
  if ROOT_DIR=$(git rev-parse --show-toplevel 2>/dev/null); then
    cd "$ROOT_DIR"
  else
    ROOT_DIR=$(pwd)
    log "warning: git root not found; using current directory"
  fi
else
  ROOT_DIR=$(pwd)
  log "warning: git not available; using current directory"
fi

export PYTHONPATH="$ROOT_DIR"
export PYTHONNOUSERSITE=1

POSTGRES_PORT=${POSTGRES_PORT:-5432}
API_PORT=${API_PORT:-8000}
export POSTGRES_PORT

if [ -z "${DATABASE_URL:-}" ]; then
  export DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:${POSTGRES_PORT}/central_achat_publique"
fi

if ! command -v lsof >/dev/null 2>&1; then
  log_ports "lsof not available; cannot check ports"
  exit 1
fi

port_in_use() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

free_port_if_needed() {
  local port="$1"
  log_ports "checking port ${port}"

  if command -v docker >/dev/null 2>&1; then
    if docker ps >/dev/null 2>&1; then
      local docker_hits=()
      while IFS=$'\t' read -r cid cname cports; do
        if [[ "$cports" == *":${port}->"* ]]; then
          docker_hits+=("$cid|$cname|$cports")
        fi
      done < <(docker ps --format '{{.ID}}\t{{.Names}}\t{{.Ports}}')

      if [ ${#docker_hits[@]} -gt 0 ]; then
        log_docker "containers exposing port ${port}:"
        for entry in "${docker_hits[@]}"; do
          IFS="|" read -r cid cname cports <<<"$entry"
          log_docker "stop ${cname} (${cid}) ${cports}"
          docker stop "$cid"
        done
      fi
    else
      log_docker "docker not running or not accessible"
    fi
  else
    log_docker "docker not available"
  fi

  if port_in_use "$port"; then
    log_ports "port ${port} still in use; checking local processes"
    lsof -nP -iTCP:"$port" -sTCP:LISTEN

    if command -v brew >/dev/null 2>&1; then
      local services=(postgresql@16 postgresql@15 postgresql)
      for svc in "${services[@]}"; do
        if brew services list | awk '{print $1}' | grep -qx "$svc"; then
          log_brew "stopping ${svc}"
          brew services stop "$svc"
        fi
      done
    else
      log_brew "brew not available"
    fi
  fi

  if port_in_use "$port"; then
    log_ports "port ${port} still occupied after cleanup; aborting"
    lsof -nP -iTCP:"$port" -sTCP:LISTEN
    exit 1
  fi

  log_ports "port ${port} is free"
}

resolve_python() {
  PY="$ROOT_DIR/.venv/bin/python"
  PIP="$ROOT_DIR/.venv/bin/pip"
  ALEMBIC="$ROOT_DIR/.venv/bin/alembic"
  UVICORN="$ROOT_DIR/.venv/bin/uvicorn"

  if [[ "$PY" == *".platformio"* ]]; then
    log_py "warning: resolved python points to platformio env: ${PY}"
  fi

  log_py "using python: ${PY}"
}

ensure_deps() {
  local need_install=0

  if [ ! -x "$ALEMBIC" ]; then
    need_install=1
  fi

  if ! "$PY" - <<'PY' >/dev/null 2>&1
import fastapi  # noqa: F401
import sqlalchemy  # noqa: F401
PY
  then
    need_install=1
  fi

  if [ "$need_install" -eq 1 ]; then
    log_deps "installing dependencies"
    if ! "$PY" -m pip install -U pip; then
      log_deps "pip upgrade failed; check network or proxy"
      exit 1
    fi
    if ! "$PY" -m pip install -e .; then
      log_deps "pip install failed; ensure you are online and have access"
      exit 1
    fi
  else
    log_deps "dependencies already installed"
  fi
}

wait_for_postgres() {
  local timeout_seconds=60
  local start_ts
  start_ts=$(date +%s)

  local cid
  cid=$(docker compose ps -q postgres)
  if [ -z "$cid" ]; then
    log_db "postgres container not found"
    exit 1
  fi

  while true; do
    local health
    health=$(docker inspect -f '{{.State.Health.Status}}' "$cid" 2>/dev/null || true)
    if [ -n "$health" ]; then
      if [ "$health" = "healthy" ]; then
        log_db "postgres healthy"
        return
      fi
      log_db "health status: ${health}"
    else
      if docker compose exec -T postgres pg_isready -U postgres >/dev/null 2>&1; then
        log_db "postgres ready (pg_isready)"
        return
      fi
    fi

    if [ $(( $(date +%s) - start_ts )) -ge "$timeout_seconds" ]; then
      log_db "timeout waiting for postgres health"
      docker compose logs postgres --tail=200
      exit 1
    fi
    sleep 2
  done
}

check_api_port() {
  local port="$1"
  if port_in_use "$port"; then
    log_ports "API port ${port} already in use; aborting"
    lsof -nP -iTCP:"$port" -sTCP:LISTEN
    exit 1
  fi
}

free_port_if_needed "$POSTGRES_PORT"
check_api_port "$API_PORT"
assert_venv
resolve_python
ensure_deps

if ! command -v docker >/dev/null 2>&1; then
  log_docker "docker not available; cannot start postgres"
  exit 1
fi

log_db "starting postgres via docker compose"
docker compose up -d postgres
wait_for_postgres

log_db "running migrations"
"$ALEMBIC" -c alembic.ini upgrade head

log "starting api on port ${API_PORT}"
exec "$PY" -m uvicorn apps.api.main:app --host 0.0.0.0 --port "$API_PORT" --reload
