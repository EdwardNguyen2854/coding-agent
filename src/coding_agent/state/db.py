"""SQLite database connection and query utilities."""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Iterator

_log = logging.getLogger(__name__)


class Database:
    """SQLite database connection wrapper with transaction support."""

    def __init__(self, db_path: Path) -> None:
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file.
        """
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._connect()
        self._init_pragmas()

    def _connect(self) -> None:
        """Establish database connection."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def _init_pragmas(self) -> None:
        """Configure database pragmas."""
        if self._conn is None:
            return
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

    @property
    def connection(self) -> sqlite3.Connection:
        """Get the underlying connection."""
        if self._conn is None:
            raise RuntimeError("Database not connected")
        return self._conn

    def execute(self, query: str, params: tuple | dict | None = None) -> sqlite3.Cursor:
        """Execute a parameterized query.

        Args:
            query: SQL query with ? or :named placeholders.
            params: Query parameters.

        Returns:
            Cursor object.
        """
        if self._conn is None:
            raise RuntimeError("Database not connected")
        
        # Handle multiple statements (split by semicolon)
        statements = [s.strip() for s in query.split(";") if s.strip()]
        if len(statements) > 1:
            # Execute each statement separately
            for stmt in statements[:-1]:  # All but last (last one will be handled by regular execute)
                self._conn.execute(stmt, params or ())
            return self._conn.execute(statements[-1], params or ())
        
        return self._conn.execute(query, params or ())

    def executemany(self, query: str, params: Iterator[tuple]) -> sqlite3.Cursor:
        """Execute a parameterized query multiple times.

        Args:
            query: SQL query with ? or :named placeholders.
            params: Iterator of parameter tuples.

        Returns:
            Cursor object.
        """
        if self._conn is None:
            raise RuntimeError("Database not connected")
        return self._conn.executemany(query, params)

    def commit(self) -> None:
        """Commit the current transaction."""
        if self._conn is not None:
            self._conn.commit()

    def rollback(self) -> None:
        """Rollback the current transaction."""
        if self._conn is not None:
            self._conn.rollback()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

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
