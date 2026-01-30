import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from shared.db.settings import get_db_settings


def db_available(retries: int = 5, delay: float = 0.5) -> bool:
    settings = get_db_settings()
    engine = create_engine(settings.database_url)
    for _ in range(retries):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except OperationalError:
            time.sleep(delay)
    return False
