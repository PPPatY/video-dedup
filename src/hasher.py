"""File hashing utilities for duplicate detection."""
import hashlib
from pathlib import Path
from dataclasses import dataclass

PARTIAL_HASH_SIZE = 65536  # 64KB

@dataclass
class FileHashInfo:
    """Information about a file's hashes."""
    path: Path
    size: int
    partial_hash: str
    full_hash: str | None = None

def compute_partial_hash(file_path: Path, size: int = PARTIAL_HASH_SIZE) -> str:
    """
    Compute SHA-256 hash of first N bytes of file.

    Args:
        file_path: Path to file
        size: Number of bytes to hash (default 64KB)

    Returns:
        Hex digest of SHA-256 hash
    """
    hasher = hashlib.sha256()

    with open(file_path, 'rb') as f:
        chunk = f.read(size)
        hasher.update(chunk)

    return hasher.hexdigest()

def compute_full_hash(file_path: Path) -> str:
    """
    Compute SHA-256 hash of entire file.

    Args:
        file_path: Path to file

    Returns:
        Hex digest of SHA-256 hash
    """
    hasher = hashlib.sha256()
    block_size = 65536  # 64KB blocks

    with open(file_path, 'rb') as f:
        while chunk := f.read(block_size):
            hasher.update(chunk)

    return hasher.hexdigest()
