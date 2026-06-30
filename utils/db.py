import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

load_dotenv()


def _build_url() -> str:
    """Build a SQLAlchemy connection URL from environment variables."""
    return (
        f"postgresql+psycopg2://{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}"
        f"@{os.environ['DB_HOST']}:{os.environ.get('DB_PORT', '5432')}"
        f"/{os.environ['DB_NAME']}"
    )


# Single engine per process — call get_engine() everywhere instead of creating new ones.
_engine = None


def get_engine():
    """Return the shared SQLAlchemy engine, creating it on first call."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            _build_url(),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            echo=False,
        )
    return _engine


def get_session_factory():
    """Return a SQLAlchemy sessionmaker bound to the shared engine."""
    return sessionmaker(bind=get_engine())


@contextmanager
def get_connection():
    """Yield a raw DBAPI connection for bulk operations (COPY, executemany)."""
    engine = get_engine()
    with engine.connect() as conn:
        yield conn


def run_sql_file(path: str, params: dict | None = None) -> None:
    """Execute a .sql file, optionally with named :param bindings."""
    with open(path, "r", encoding="utf-8") as f:
        sql = f.read()
    with get_engine().begin() as conn:
        conn.execute(text(sql), params or {})


def query_df(sql: str, params: dict | None = None):
    """Return a DataFrame from a SQL string or named :param query."""
    import pandas as pd
    with get_engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def query_sql_file(path: str, params: dict | None = None):
    """Read a .sql file and return results as a DataFrame."""
    with open(path, "r", encoding="utf-8") as f:
        sql = f.read()
    return query_df(sql, params)


def test_connection() -> None:
    """Verify the database connection by running SELECT 1 and printing the result."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Connection successful!")
    except Exception as e:
        print(f"Connection failed: {e}")


if __name__ == "__main__":
    test_connection()
