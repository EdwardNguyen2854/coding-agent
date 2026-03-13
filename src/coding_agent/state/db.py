"""SQLite database connection and query utilities."""

from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Iterator

_log = logging.getLogger(__name__)


class Database:
    """SQLite database connection wrapper with thread-local connections.

    Each thread that accesses the database gets its own SQLite connection,
    which is the correct pattern for SQLite's threading model.  WAL mode is
    enabled so concurrent readers don't block writers across threads.
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize database.

        Args:
            db_path: Path to SQLite database file.
        """
        self._db_path = db_path
        self._local = threading.local()
        # Create the file and apply schema pragmas on the calling thread.
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_pragmas()

    def _get_conn(self) -> sqlite3.Connection:
        """Return the connection for the current thread, creating it if needed."""
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return conn

    def _init_pragmas(self) -> None:
        """Configure database pragmas on the calling thread's connection."""
        self._get_conn()

    @property
    def connection(self) -> sqlite3.Connection:
        """Get the current thread's connection."""
        return self._get_conn()

    def execute(self, query: str, params: tuple | dict | None = None) -> sqlite3.Cursor:
        """Execute a parameterized query.

        Args:
            query: SQL query with ? or :named placeholders.
            params: Query parameters.

        Returns:
            Cursor object.
        """
        conn = self._get_conn()
        # Handle multiple statements (split by semicolon)
        statements = [s.strip() for s in query.split(";") if s.strip()]
        if len(statements) > 1:
            # Execute each statement separately; params apply only to the last statement
            for stmt in statements[:-1]:
                conn.execute(stmt)
            return conn.execute(statements[-1], params or ())

        return conn.execute(query, params or ())

    def executemany(self, query: str, params: Iterator[tuple]) -> sqlite3.Cursor:
        """Execute a parameterized query multiple times.

        Args:
            query: SQL query with ? or :named placeholders.
            params: Iterator of parameter tuples.

        Returns:
            Cursor object.
        """
        return self._get_conn().executemany(query, params)

    def commit(self) -> None:
        """Commit the current thread's transaction."""
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is not None:
            conn.commit()

    def rollback(self) -> None:
        """Rollback the current thread's transaction."""
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is not None:
            conn.rollback()

    def close(self) -> None:
        """Close the current thread's connection."""
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    @contextmanager
    def transaction(self) -> Generator[None, None, None]:
        """Context manager for transactions.

        Yields:
            None.
        """
        try:
            yield
            self.commit()
        except Exception:
            self.rollback()
            raise

    def get_schema_migrations(self) -> list[int]:
        """Get list of applied schema migration versions.

        Returns:
            List of applied version numbers.
        """
        rows = self.execute("SELECT version FROM schema_migrations ORDER BY version")
        return [row[0] for row in rows]

    def add_migration(self, version: int) -> None:
        """Record a schema migration as applied.

        Args:
            version: Migration version number.
        """
        now = datetime.now(timezone.utc).isoformat()
        self.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (version, now),
        )
        self.commit()

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists.

        Args:
            table_name: Name of the table.

        Returns:
            True if table exists.
        """
        result = self.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return result.fetchone() is not None

    def vacuum(self) -> None:
        """Run VACUUM to optimize database."""
        self.execute("VACUUM")
        self.commit()
