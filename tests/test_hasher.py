from pathlib import Path

def test_compute_partial_hash_first_64kb(temp_dir, create_test_file):
    """Test computing hash of first 64KB."""
    from src.hasher import compute_partial_hash

    # Create file with known content
    content = b"A" * 100_000  # 100KB
    file_path = create_test_file(temp_dir, "video.mp4", content)

    hash1 = compute_partial_hash(file_path)

    # Hash should be consistent
    hash2 = compute_partial_hash(file_path)
    assert hash1 == hash2

    # Hash should be 64-character SHA-256 hex string
    assert len(hash1) == 64
    assert all(c in '0123456789abcdef' for c in hash1)

def test_compute_partial_hash_small_file(temp_dir, create_test_file):
    """Test partial hash on files smaller than 64KB."""
    from src.hasher import compute_partial_hash

    content = b"small content"
    file_path = create_test_file(temp_dir, "small.mp4", content)

    partial_hash = compute_partial_hash(file_path)

    # Should hash entire file content
    import hashlib
    expected = hashlib.sha256(content).hexdigest()
    assert partial_hash == expected

def test_compute_full_hash(temp_dir, create_test_file):
    """Test computing full file hash."""
    from src.hasher import compute_full_hash

    content = b"full content for hashing"
    file_path = create_test_file(temp_dir, "video.mp4", content)

    full_hash = compute_full_hash(file_path)

    # Verify against known hash
    import hashlib
    expected = hashlib.sha256(content).hexdigest()
    assert full_hash == expected

def test_identical_files_produce_same_hash(temp_dir, create_test_file):
    """Test that identical files produce identical hashes."""
    from src.hasher import compute_full_hash

    content = b"identical content"
    file1 = create_test_file(temp_dir, "file1.mp4", content)
    file2 = create_test_file(temp_dir, "file2.mp4", content)

    hash1 = compute_full_hash(file1)
    hash2 = compute_full_hash(file2)

    assert hash1 == hash2

def test_different_files_produce_different_hash(temp_dir, create_test_file):
    """Test that different files produce different hashes."""
    from src.hasher import compute_full_hash

    file1 = create_test_file(temp_dir, "file1.mp4", b"content1")
    file2 = create_test_file(temp_dir, "file2.mp4", b"content2")

    hash1 = compute_full_hash(file1)
    hash2 = compute_full_hash(file2)

    assert hash1 != hash2

def test_compute_hash_file_not_found(temp_dir):
    """Test hashing non-existent file raises FileNotFoundError."""
    from src.hasher import compute_full_hash
    from pathlib import Path
    import pytest

    non_existent = temp_dir / "does_not_exist.mp4"

    with pytest.raises(FileNotFoundError):
        compute_full_hash(non_existent)

def test_compute_hash_large_file(temp_dir, create_test_file):
    """Test hashing a larger file (simulating real video)."""
    from src.hasher import compute_full_hash, compute_partial_hash

    # Create 5MB file
    content = b"X" * (5 * 1024 * 1024)
    file_path = create_test_file(temp_dir, "large.mp4", content)

    partial = compute_partial_hash(file_path)
    full = compute_full_hash(file_path)

    # Partial and full should differ (partial only hashes first 64KB)
    assert partial != full
    assert len(full) == 64
