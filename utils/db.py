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
  pool_status()        — dict of live pool metrics
  test_connection()    — smoke-test the DB credentials
"""

import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

_PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
_PERF_LOG = _PROCESSED_DIR / "query_performance.csv"
_PERF_LOG_ENABLED = True

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

    Pool settings:
      pool_size=5        — keep 5 persistent connections open
      max_overflow=10    — allow up to 10 additional burst connections
      pool_timeout=30    — raise after 30 s waiting for a free slot
      pool_recycle=3600  — replace connections older than 1 h to avoid
                           PostgreSQL's idle timeout closing them underneath
      pool_pre_ping=True — test each connection before use to discard stale ones

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
            pool_timeout=30,
            pool_recycle=3600,
            echo=False,
        )
        logger.info(
            "Connection pool initialised: size=%d max_overflow=%d "
            "timeout=%ds recycle=%ds",
            5, 10, 30, 3600,
        )
    return _engine


def pool_status() -> dict:
    """Return live metrics from the connection pool.

    Returns a dict with keys: size, checkedin, checkedout, overflow, invalid.
    Returns an empty dict if the engine has not been initialised yet.
    """
    if _engine is None:
        return {}
    pool = _engine.pool
    status = {
        "size": pool.size(),
        "checkedin": pool.checkedin(),
        "checkedout": pool.checkedout(),
        "overflow": pool.overflow(),
        "invalid": pool.invalidated if hasattr(pool, "invalidated") else 0,
    }
    logger.debug("Pool status: %s", status)
    return status


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


def _log_query_perf(sql: str, duration_s: float) -> None:
    """Append one row to query_performance.csv; alert if > 5 s."""
    if not _PERF_LOG_ENABLED:
        return
    try:
        _PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        import csv
        from datetime import datetime as _dt

        preview = " ".join(sql.split())[:120]
        duration_ms = round(duration_s * 1000, 1)
        if duration_s > 5:
            logger.warning("SLOW QUERY (%.1f s): %s", duration_s, preview)

        write_header = not _PERF_LOG.exists()
        with open(_PERF_LOG, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(["timestamp", "duration_ms", "query_preview"])
            w.writerow([_dt.now().isoformat(), duration_ms, preview])
    except Exception:
        pass


def query_df(sql: str, params: dict | None = None):
    """Execute a SQL query and return the results as a pandas DataFrame.

    Args:
        sql:    A SQL string, optionally with :name parameter placeholders.
        params: Optional dict of named parameters to bind into the query.

    Returns:
        A pandas DataFrame containing all result rows and columns.
    """
    import pandas as pd

    t0 = time.perf_counter()
    with get_engine().connect() as conn:
        result = pd.read_sql(text(sql), conn, params=params or {})
    _log_query_perf(sql, time.perf_counter() - t0)
    return result


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

    Prints connection status and pool metrics.
    Run this module directly (python utils/db.py) to smoke-test credentials.
    """
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Connection successful!")
        status = pool_status()
        print(f"Pool status: size={status.get('size')} checkedin={status.get('checkedin')} "
              f"checkedout={status.get('checkedout')} overflow={status.get('overflow')}")
    except Exception as e:
        print(f"Connection failed: {e}")


if __name__ == "__main__":
    test_connection()
