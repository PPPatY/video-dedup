from pathlib import Path
import sqlite3
import time

def test_cache_creates_database(temp_dir):
    """Test that Cache creates SQLite database file."""
    from src.cache import Cache

    cache_dir = temp_dir / "cache"
    cache = Cache(cache_dir)

    db_path = cache_dir / "hashes.db"
    assert db_path.exists()

    # Verify table exists
    conn = sqlite3.connect(db_path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='file_hashes'"
    )
    assert cursor.fetchone() is not None
    conn.close()

def test_cache_miss_returns_none(temp_dir):
    """Test cache miss returns None."""
    from src.cache import Cache
    from pathlib import Path

    cache = Cache(temp_dir / "cache")

    result = cache.get_hash(Path("/some/file.mp4"), 1000, 1234567890.0)

    assert result is None
    assert cache.get_stats()["miss_count"] == 1

def test_cache_hit_returns_hash(temp_dir, create_test_file):
    """Test cache hit returns stored hash."""
    from src.cache import Cache
    import os

    cache = Cache(temp_dir / "cache")

    file_path = create_test_file(temp_dir, "video.mp4", b"content")
    stat = os.stat(file_path)

    # Store hash
    cache.store_hash(file_path, stat.st_size, stat.st_mtime, "abc123hash")

    # Retrieve hash
    result = cache.get_hash(file_path, stat.st_size, stat.st_mtime)

    assert result == "abc123hash"
    assert cache.get_stats()["hit_count"] == 1

def test_cache_miss_after_file_modification(temp_dir, create_test_file):
    """Test cache miss when file is modified."""
    from src.cache import Cache
    import os

    cache = Cache(temp_dir / "cache")

    file_path = create_test_file(temp_dir, "video.mp4", b"original")
    stat1 = os.stat(file_path)

    # Store original hash
    cache.store_hash(file_path, stat1.st_size, stat1.st_mtime, "hash1")

    # Modify file (change mtime)
    time.sleep(0.01)  # Ensure mtime changes
    file_path.write_bytes(b"modified")
    stat2 = os.stat(file_path)

    # Should be cache miss with new mtime
    result = cache.get_hash(file_path, stat2.st_size, stat2.st_mtime)

    assert result is None
    assert cache.get_stats()["miss_count"] == 1

def test_update_last_seen(temp_dir, create_test_file):
    """Test updating last_seen timestamp."""
    from src.cache import Cache
    import os
    import sqlite3

    cache = Cache(temp_dir / "cache")

    file_path = create_test_file(temp_dir, "video.mp4", b"content")
    stat = os.stat(file_path)

    cache.store_hash(file_path, stat.st_size, stat.st_mtime, "hash1")

    # Get initial last_seen
    conn = sqlite3.connect(cache.db_path)
    cursor = conn.execute("SELECT last_seen FROM file_hashes WHERE path=?", (str(file_path.resolve()),))
    last_seen_1 = cursor.fetchone()[0]
    conn.close()

    # Wait and update
    time.sleep(0.01)
    cache.update_last_seen(file_path)

    # Verify last_seen changed
    conn = sqlite3.connect(cache.db_path)
    cursor = conn.execute("SELECT last_seen FROM file_hashes WHERE path=?", (str(file_path.resolve()),))
    last_seen_2 = cursor.fetchone()[0]
    conn.close()

    assert last_seen_2 > last_seen_1

def test_cache_hit_updates_last_seen(temp_dir, create_test_file):
    """Looking up a valid hash refreshes retention without a second DB call."""
    from src.cache import Cache
    import os
    import sqlite3

    cache = Cache(temp_dir / "cache")
    file_path = create_test_file(temp_dir, "video.mp4", b"content")
    stat = os.stat(file_path)
    cache.store_hash(file_path, stat.st_size, stat.st_mtime, "hash1")

    conn = sqlite3.connect(cache.db_path)
    conn.execute("UPDATE file_hashes SET last_seen=0")
    conn.commit()
    conn.close()

    assert cache.get_hash(file_path, stat.st_size, stat.st_mtime) == "hash1"
    conn = sqlite3.connect(cache.db_path)
    last_seen = conn.execute("SELECT last_seen FROM file_hashes").fetchone()[0]
    conn.close()
    assert last_seen > 0

def test_clean_old_entries(temp_dir, create_test_file):
    """Test cleaning entries older than N days."""
    from src.cache import Cache
    import os
    import sqlite3

    cache = Cache(temp_dir / "cache")

    file_path = create_test_file(temp_dir, "video.mp4", b"content")
    stat = os.stat(file_path)

    cache.store_hash(file_path, stat.st_size, stat.st_mtime, "hash1")

    # Manually set last_seen to 31 days ago
    old_timestamp = time.time() - (31 * 24 * 3600)
    conn = sqlite3.connect(cache.db_path)
    conn.execute("UPDATE file_hashes SET last_seen=?", (old_timestamp,))
    conn.commit()
    conn.close()

    # Clean entries older than 30 days
    cache.clean_old_entries(days=30)

    # Entry should be removed
    result = cache.get_hash(file_path, stat.st_size, stat.st_mtime)
    assert result is None

def test_clear_all_entries(temp_dir, create_test_file):
    """Test clearing all cache entries."""
    from src.cache import Cache
    import os
    import sqlite3

    cache = Cache(temp_dir / "cache")

    file_path = create_test_file(temp_dir, "video.mp4", b"content")
    stat = os.stat(file_path)

    cache.store_hash(file_path, stat.st_size, stat.st_mtime, "hash1")

    # Clear cache
    cache.clear()

    # Verify no entries
    conn = sqlite3.connect(cache.db_path)
    cursor = conn.execute("SELECT COUNT(*) FROM file_hashes")
    count = cursor.fetchone()[0]
    conn.close()

    assert count == 0
