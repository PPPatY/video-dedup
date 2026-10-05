"""File retention rule selector."""
from pathlib import Path
import os

TIME_SIMILARITY_THRESHOLD = 86400  # 24 hours in seconds

def select_files_to_keep(duplicate_groups: list[list[Path]]) -> dict[Path, list[Path]]:
    """
    Select which files to keep from duplicate groups.

    Rules (in priority order):
    1. Keep oldest file (by mtime)
    2. If mtimes within 24h, keep shortest path
    3. If path lengths equal, keep lexicographically first

    Args:
        duplicate_groups: List of duplicate file groups

    Returns:
        Dictionary mapping file_to_keep -> [files_to_delete]
    """
    result = {}

    for group in duplicate_groups:
        if len(group) < 2:
            continue

        # Sort by mtime (oldest first)
        sorted_files = sorted(group, key=lambda f: os.path.getmtime(f))
        oldest_file = sorted_files[0]
        oldest_mtime = os.path.getmtime(oldest_file)

        # Find files with similar time (within 24 hours)
        similar_time_files = [
            f for f in sorted_files
            if abs(os.path.getmtime(f) - oldest_mtime) < TIME_SIMILARITY_THRESHOLD
        ]

        if len(similar_time_files) > 1:
            # Multiple files with similar time - use shortest path
            # If paths same length, use lexicographic order
            to_keep = min(similar_time_files, key=lambda f: (len(str(f)), str(f)))
        else:
            # Keep the oldest
            to_keep = oldest_file

        to_delete = [f for f in group if f != to_keep]
        result[to_keep] = to_delete

    return result
