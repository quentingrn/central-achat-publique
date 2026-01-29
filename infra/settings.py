import os
from dataclasses import dataclass

from shared.db.settings import get_db_settings


@dataclass(frozen=True)
class AppSettings:
    environment: str
    database_url: str
    allow_db_drift: bool


def get_settings() -> AppSettings:
    db = get_db_settings()
    return AppSettings(
        environment=os.getenv("APP_ENV", "dev"),
        database_url=db.database_url,
        allow_db_drift=db.allow_db_drift,
    )
