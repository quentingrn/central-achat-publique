import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DBSettings:
    database_url: str
    allow_db_drift: bool


def get_db_settings() -> DBSettings:
    return DBSettings(
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5432/central_achat_publique",
        ),
        allow_db_drift=os.getenv("ALLOW_DB_DRIFT", "0") == "1",
    )
