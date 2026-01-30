from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from shared.db.settings import get_db_settings

_engine = None
_SessionLocal = None


def _init_engine() -> None:
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_db_settings()
        _engine = create_engine(settings.database_url)
        _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


def get_session() -> Session:
    _init_engine()
    assert _SessionLocal is not None
    return _SessionLocal()
