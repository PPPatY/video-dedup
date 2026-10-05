"""File system scanner for video files."""
from pathlib import Path
from typing import Iterator
from src.utils import VIDEO_EXTENSIONS

def scan_files(
    root_dirs: list[Path],
    exclude_patterns: list[str] = None,
    follow_symlinks: bool = False,
    include_hidden: bool = False
) -> Iterator[Path]:
    """
    Scan directories recursively for video files.

    Args:
        root_dirs: List of directories to scan
        exclude_patterns: Directory name patterns to exclude
        follow_symlinks: Whether to follow symbolic links
        include_hidden: Whether to include hidden files/directories

    Yields:
        Absolute paths to video files
    """
    exclude_patterns = exclude_patterns or []

    for root_dir in root_dirs:
        yield from _scan_directory(
            root_dir, exclude_patterns, follow_symlinks, include_hidden, set()
        )

def _scan_directory(
    directory: Path,
    exclude_patterns: list[str],
    follow_symlinks: bool,
    include_hidden: bool,
    visited_inodes: set
) -> Iterator[Path]:
    """Recursively scan a single directory."""
    try:
        for entry in directory.iterdir():
            # Skip hidden files/directories
            if not include_hidden and entry.name.startswith('.'):
                continue

            if entry.is_dir(follow_symlinks=False):
                # Check exclude patterns
                if any(entry.name == pattern for pattern in exclude_patterns):
                    continue

                # Handle symlinks
                if entry.is_symlink():
                    if not follow_symlinks:
                        continue
                    # Check for loops
                    stat = entry.stat()
                    inode = (stat.st_dev, stat.st_ino)
                    if inode in visited_inodes:
                        continue
                    visited_inodes.add(inode)

                yield from _scan_directory(
                    entry, exclude_patterns, follow_symlinks, include_hidden, visited_inodes
                )

            elif entry.is_file():
                if entry.suffix.lower() in VIDEO_EXTENSIONS:
                    yield entry.resolve()

    except PermissionError:
        # Skip directories we can't access
        pass
