import os
import time

def test_group_by_size(temp_dir, create_test_file):
    """Test grouping files by size."""
    from src.grouper import group_by_size

    file1 = create_test_file(temp_dir, "file1.mp4", b"12345")  # 5 bytes
    file2 = create_test_file(temp_dir, "file2.mp4", b"12345")  # 5 bytes
    file3 = create_test_file(temp_dir, "file3.mp4", b"123")    # 3 bytes

    groups = group_by_size([file1, file2, file3])

    assert len(groups) == 2
    assert len(groups[5]) == 2
    assert len(groups[3]) == 1

def test_group_by_hash(temp_dir, create_test_file):
    """Test grouping files by hash."""
    from src.grouper import group_by_hash
    from src.hasher import compute_full_hash

    # Two identical, one different
    file1 = create_test_file(temp_dir, "file1.mp4", b"same content")
    file2 = create_test_file(temp_dir, "file2.mp4", b"same content")
    file3 = create_test_file(temp_dir, "file3.mp4", b"different")

    groups = group_by_hash([file1, file2, file3], compute_full_hash)

    assert len(groups) == 2
    # Find group with 2 files (identical)
    duplicate_group = [g for g in groups.values() if len(g) == 2][0]
    assert set(duplicate_group) == {file1, file2}

def test_group_by_hash_supports_parallel_workers(temp_dir, create_test_file):
    """Hash grouping can use multiple workers without changing results."""
    from src.grouper import group_by_hash
    from src.hasher import compute_full_hash

    file1 = create_test_file(temp_dir, "file1.mp4", b"same content")
    file2 = create_test_file(temp_dir, "file2.mp4", b"same content")
    file3 = create_test_file(temp_dir, "file3.mp4", b"different")

    groups = group_by_hash([file1, file2, file3], compute_full_hash, workers=2)

    duplicate_group = [group for group in groups.values() if len(group) == 2][0]
    assert set(duplicate_group) == {file1, file2}

def test_find_duplicates_three_stage(temp_dir, create_test_file):
    """Test finding duplicates using three-stage progressive hashing."""
    from src.grouper import find_duplicates

    # Create test files
    # Group 1: truly identical
    file1a = create_test_file(temp_dir, "dup1a.mp4", b"A" * 100000)
    file1b = create_test_file(temp_dir, "dup1b.mp4", b"A" * 100000)

    # Group 2: same size, different content
    file2a = create_test_file(temp_dir, "diff2a.mp4", b"B" * 100000)
    file2b = create_test_file(temp_dir, "diff2b.mp4", b"C" * 100000)

    # Unique file
    file3 = create_test_file(temp_dir, "unique.mp4", b"D" * 50000)

    duplicates = find_duplicates([file1a, file1b, file2a, file2b, file3])

    # Should find exactly 1 duplicate group (file1a, file1b)
    assert len(duplicates) == 1
    assert set(duplicates[0]) == {file1a, file1b}

def test_find_duplicates_same_size_different_content(temp_dir, create_test_file):
    """Test that files with same size but different content are not marked as duplicates."""
    from src.grouper import find_duplicates

    # Create two files with same size but different content
    file1 = create_test_file(temp_dir, "file1.mp4", b"A" * 1000)
    file2 = create_test_file(temp_dir, "file2.mp4", b"B" * 1000)

    # Set same mtime
    mtime = time.time()
    os.utime(file1, (mtime, mtime))
    os.utime(file2, (mtime, mtime))

    # Verify they have same size and mtime
    stat1 = os.stat(file1)
    stat2 = os.stat(file2)
    assert stat1.st_size == stat2.st_size
    assert stat1.st_mtime == stat2.st_mtime

    duplicates = find_duplicates([file1, file2])

    # Should NOT be marked as duplicates
    assert len(duplicates) == 0

def test_find_duplicates_uses_cache(temp_dir, create_test_file):
    """Test that find_duplicates uses cache when provided."""
    from src.grouper import find_duplicates
    from src.cache import Cache
    from src.hasher import compute_full_hash

    cache = Cache(temp_dir / "cache")

    # Create identical files
    file1 = create_test_file(temp_dir, "file1.mp4", b"content")
    file2 = create_test_file(temp_dir, "file2.mp4", b"content")

    # Pre-populate cache
    stat1 = os.stat(file1)
    hash1 = compute_full_hash(file1)
    cache.store_hash(file1, stat1.st_size, stat1.st_mtime, hash1)

    # Find duplicates (should use cache for file1)
    duplicates = find_duplicates([file1, file2], cache=cache)

    assert len(duplicates) == 1
    assert set(duplicates[0]) == {file1, file2}

    # Verify cache was used (at least one hit)
    stats = cache.get_stats()
    assert stats["hit_count"] >= 1
