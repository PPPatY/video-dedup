"""SQLite cache for file hash storage."""
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

class Cache:
    """SQLite-based cache for file hashes."""

    def __init__(self, cache_dir: Path):
        """
        Initialize cache.

        Args:
            cache_dir: Directory to store cache database
        """
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = cache_dir / "hashes.db"
        self.hit_count = 0
        self.miss_count = 0
        self._stats_lock = threading.Lock()

        self._init_database()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Open a connection for one operation and always release it."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_database(self):
        """Create database tables and indexes."""
        with self._connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_hashes (
                    path TEXT PRIMARY KEY,
                    size INTEGER NOT NULL,
                    mtime REAL NOT NULL,
                    full_hash TEXT NOT NULL,
                    partial_hash TEXT,
                    last_seen REAL NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_full_hash ON file_hashes(full_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_last_seen ON file_hashes(last_seen)")

    def get_hash(self, file_path: Path, size: int, mtime: float) -> str | None:
        """
        Get cached hash if file unchanged.

        Args:
            file_path: Absolute path to file
            size: File size in bytes
            mtime: File modification timestamp

        Returns:
            Cached hash if found and valid, None otherwise
        """
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT full_hash FROM file_hashes WHERE path=? AND size=? AND mtime=?",
                (str(file_path.resolve()), size, mtime)
            )
            row = cursor.fetchone()
            if row:
                conn.execute(
                    "UPDATE file_hashes SET last_seen=? WHERE path=?",
                    (time.time(), str(file_path.resolve()))
                )

        if row:
            with self._stats_lock:
                self.hit_count += 1
            return row[0]
        else:
            with self._stats_lock:
                self.miss_count += 1
            return None

    def store_hash(
        self,
        file_path: Path,
        size: int,
        mtime: float,
        full_hash: str,
        partial_hash: str | None = None,
    ):
        """
        Store hash in cache.

        Args:
            file_path: Absolute path to file
            size: File size in bytes
            mtime: File modification timestamp
            full_hash: SHA-256 full hash
            partial_hash: Optional partial hash
        """
        now = time.time()
        with self._connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO file_hashes
                (path, size, mtime, full_hash, partial_hash, last_seen, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (str(file_path.resolve()), size, mtime, full_hash, partial_hash, now, now))

    def update_last_seen(self, file_path: Path):
        """
        Update last_seen timestamp for file.

        Args:
            file_path: Absolute path to file
        """
        now = time.time()
        with self._connection() as conn:
            conn.execute(
                "UPDATE file_hashes SET last_seen=? WHERE path=?",
                (now, str(file_path.resolve()))
            )

    def clean_old_entries(self, days: int = 30):
        """
        Remove cache entries not seen in N days.

        Args:
            days: Number of days threshold
        """
        cutoff = time.time() - (days * 24 * 3600)
        with self._connection() as conn:
            conn.execute("DELETE FROM file_hashes WHERE last_seen < ?", (cutoff,))

    def clear(self):
        """Clear all cache entries."""
        with self._connection() as conn:
            conn.execute("DELETE FROM file_hashes")

    def get_stats(self) -> dict[str, int]:
        """Get cache statistics."""
        with self._stats_lock:
            return {"hit_count": self.hit_count, "miss_count": self.miss_count}
