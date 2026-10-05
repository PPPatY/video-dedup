"""Duplicate file grouping logic."""
from pathlib import Path
from collections import defaultdict
from typing import Callable
import os
from src.hasher import compute_partial_hash, compute_full_hash

def group_by_size(files: list[Path]) -> dict[int, list[Path]]:
    """
    Group files by size.

    Args:
        files: List of file paths

    Returns:
        Dictionary mapping size to list of files
    """
    groups = defaultdict(list)
    for file_path in files:
        try:
            size = os.path.getsize(file_path)
            groups[size].append(file_path)
        except (FileNotFoundError, PermissionError):
            # Skip files we can't access
            pass
    return dict(groups)

def group_by_hash(files: list[Path], hash_func: Callable) -> dict[str, list[Path]]:
    """
    Group files by hash using provided hash function.

    Args:
        files: List of file paths
        hash_func: Function that takes Path and returns hash string

    Returns:
        Dictionary mapping hash to list of files
    """
    groups = defaultdict(list)
    for file_path in files:
        try:
            hash_value = hash_func(file_path)
            groups[hash_value].append(file_path)
        except (FileNotFoundError, PermissionError):
            # Skip files we can't access
            pass
    return dict(groups)

def find_duplicates(files: list[Path], cache=None) -> list[list[Path]]:
    """
    Find duplicate files using progressive hashing strategy.

    Stage 1: Group by size (metadata only)
    Stage 2: Group by partial hash (first 64KB)
    Stage 3: Group by full hash (entire file)

    Args:
        files: List of file paths to check
        cache: Optional Cache instance for hash lookup

    Returns:
        List of duplicate groups (each group is a list of paths)
    """
    if not files:
        return []

    # Stage 1: Group by size
    size_groups = group_by_size(files)

    # Only process groups with 2+ files
    candidates = []
    for size, file_list in size_groups.items():
        if len(file_list) > 1:
            candidates.extend(file_list)

    if not candidates:
        return []

    # Stage 2: Group by partial hash
    partial_groups = group_by_hash(candidates, compute_partial_hash)

    # Only process groups with 2+ files
    candidates = []
    for hash_val, file_list in partial_groups.items():
        if len(file_list) > 1:
            candidates.extend(file_list)

    if not candidates:
        return []

    # Stage 3: Group by full hash (with cache)
    def hash_with_cache(file_path: Path) -> str:
        if cache:
            stat = os.stat(file_path)
            cached_hash = cache.get_hash(file_path, stat.st_size, stat.st_mtime)
            if cached_hash:
                cache.update_last_seen(file_path)
                return cached_hash

        # Compute and store in cache
        full_hash = compute_full_hash(file_path)
        if cache:
            stat = os.stat(file_path)
            cache.store_hash(file_path, stat.st_size, stat.st_mtime, full_hash)

        return full_hash

    full_groups = group_by_hash(candidates, hash_with_cache)

    # Return only groups with 2+ files
    duplicates = [file_list for file_list in full_groups.values() if len(file_list) > 1]

    return duplicates
