import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DBSettings:
    database_url: str
    allow_db_drift: bool


def get_db_settings() -> DBSettings:
    env_files = _read_env_files()
    return DBSettings(
        database_url=os.getenv(
            "DATABASE_URL",
            env_files.get(
                "DATABASE_URL",
                "postgresql+psycopg://postgres:postgres@localhost:5432/central_achat_publique",
            ),
        ),
        allow_db_drift=os.getenv("ALLOW_DB_DRIFT", env_files.get("ALLOW_DB_DRIFT", "0")) == "1",
    )


def _read_env_files() -> dict[str, str]:
    values: dict[str, str] = {}
    for filename in (".env", ".env.local"):
        path = Path(filename)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip().strip("'").strip('"')
            values[key.strip()] = value
    return values
