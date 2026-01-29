import logging
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import FastAPI
from sqlalchemy import create_engine

from apps.api.middleware.request_logging import RequestLoggingMiddleware
from apps.api.middleware.trace_id import TraceIdMiddleware
from modules.discovery_compare.adapters.http.router import router as discovery_router
from shared.db.settings import get_db_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")


def _assert_db_at_head() -> None:
    settings = get_db_settings()
    if settings.allow_db_drift:
        return

    root = Path(__file__).resolve().parents[2]
    alembic_cfg = Config(str(root / "alembic.ini"))
    script = ScriptDirectory.from_config(alembic_cfg)
    head_rev = script.get_current_head()

    engine = create_engine(settings.database_url)
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        current_rev = context.get_current_revision()

    if current_rev != head_rev:
        raise RuntimeError(
            "Database schema out of date. "
            f"current={current_rev} head={head_rev}. "
            "Set ALLOW_DB_DRIFT=1 to override."
        )


app = FastAPI()
app.add_middleware(TraceIdMiddleware)
app.add_middleware(RequestLoggingMiddleware)


@app.on_event("startup")
def _startup_check() -> None:
    _assert_db_at_head()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(discovery_router)
