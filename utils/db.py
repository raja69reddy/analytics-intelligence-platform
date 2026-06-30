"""Database connection helpers for the web_analytics PostgreSQL database.

All callers should use get_engine() rather than creating their own engines.
The module-level engine is initialised once and reused across all calls in
the same process, keeping connection-pool overhead to a minimum.

Public API:
  get_engine()         — shared SQLAlchemy Engine
  get_connection()     — context manager yielding a raw Connection
  run_sql_file(path)   — execute a .sql file in one transaction
  query_df(sql)        — run a SELECT and return a DataFrame
  query_sql_file(path) — run a .sql file and return a DataFrame
  test_connection()    — smoke-test the DB credentials
"""
import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

load_dotenv()


def _build_url() -> str:
    """Build a SQLAlchemy connection URL from environment variables.

    Reads DB_USER, DB_PASSWORD, DB_HOST, DB_NAME from the environment
    (or .env file). DB_PORT defaults to 5432 if not set.

    Returns:
        A postgresql+psycopg2:// connection string.
    """
    return (
        f"postgresql+psycopg2://{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}"
        f"@{os.environ['DB_HOST']}:{os.environ.get('DB_PORT', '5432')}"
        f"/{os.environ['DB_NAME']}"
    )


# Single engine per process — call get_engine() everywhere instead of creating new ones.
_engine = None


def get_engine():
    """Return the shared SQLAlchemy engine, creating it on the first call.

    Uses a connection pool (size=5, max_overflow=10) with pool_pre_ping
    enabled so stale connections are recycled automatically.

    Returns:
        A SQLAlchemy Engine connected to the web_analytics database.
    """
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
    """Return a SQLAlchemy sessionmaker bound to the shared engine.

    Use this when you need ORM-style sessions rather than raw connections.

    Returns:
        A sessionmaker instance.
    """
    return sessionmaker(bind=get_engine())


@contextmanager
def get_connection():
    """Context manager that yields a SQLAlchemy Connection for raw SQL work.

    Preferred for bulk operations (COPY, executemany) where you want direct
    control over the transaction. The connection is returned to the pool on exit.

    Yields:
        A SQLAlchemy Connection object.
    """
    engine = get_engine()
    with engine.connect() as conn:
        yield conn


def run_sql_file(path: str, params: dict | None = None) -> None:
    """Read a .sql file from disk and execute it in a single transaction.

    The entire file is executed as one statement block. Use :name syntax
    in the SQL file for parameter substitution.

    Args:
        path:   Absolute or relative path to the .sql file.
        params: Optional dict of named parameters to bind into the query.
    """
    with open(path, "r", encoding="utf-8") as f:
        sql = f.read()
    with get_engine().begin() as conn:
        conn.execute(text(sql), params or {})


def query_df(sql: str, params: dict | None = None):
    """Execute a SQL query and return the results as a pandas DataFrame.

    Args:
        sql:    A SQL string, optionally with :name parameter placeholders.
        params: Optional dict of named parameters to bind into the query.

    Returns:
        A pandas DataFrame containing all result rows and columns.
    """
    import pandas as pd
    with get_engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def query_sql_file(path: str, params: dict | None = None):
    """Read a .sql file from disk and return query results as a DataFrame.

    Convenience wrapper combining file I/O with query_df.

    Args:
        path:   Path to a .sql file containing a SELECT statement.
        params: Optional named parameters to bind.

    Returns:
        A pandas DataFrame with the query results.
    """
    with open(path, "r", encoding="utf-8") as f:
        sql = f.read()
    return query_df(sql, params)


def test_connection() -> None:
    """Verify the database is reachable by executing SELECT 1.

    Prints 'Connection successful!' on success or an error message on failure.
    Run this module directly (python utils/db.py) to smoke-test credentials.
    """
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Connection successful!")
    except Exception as e:
        print(f"Connection failed: {e}")


if __name__ == "__main__":
    test_connection()
