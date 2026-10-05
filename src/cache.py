"""SQLite cache for file hash storage."""
import sqlite3
import time
from pathlib import Path

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

        self._init_database()

    def _init_database(self):
        """Create database tables and indexes."""
        conn = sqlite3.connect(self.db_path)
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
        conn.commit()
        conn.close()

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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT full_hash FROM file_hashes WHERE path=? AND size=? AND mtime=?",
            (str(file_path.resolve()), size, mtime)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            self.hit_count += 1
            return row[0]
        else:
            self.miss_count += 1
            return None

    def store_hash(self, file_path: Path, size: int, mtime: float, full_hash: str, partial_hash: str = None):
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
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO file_hashes
            (path, size, mtime, full_hash, partial_hash, last_seen, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (str(file_path.resolve()), size, mtime, full_hash, partial_hash, now, now))
        conn.commit()
        conn.close()

    def update_last_seen(self, file_path: Path):
        """
        Update last_seen timestamp for file.

        Args:
            file_path: Absolute path to file
        """
        now = time.time()
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE file_hashes SET last_seen=? WHERE path=?",
            (now, str(file_path.resolve()))
        )
        conn.commit()
        conn.close()

    def clean_old_entries(self, days: int = 30):
        """
        Remove cache entries not seen in N days.

        Args:
            days: Number of days threshold
        """
        cutoff = time.time() - (days * 24 * 3600)
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM file_hashes WHERE last_seen < ?", (cutoff,))
        conn.commit()
        conn.close()

    def clear(self):
        """Clear all cache entries."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM file_hashes")
        conn.commit()
        conn.close()

    def get_stats(self) -> dict[str, int]:
        """Get cache statistics."""
        return {"hit_count": self.hit_count, "miss_count": self.miss_count}
