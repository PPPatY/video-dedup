"""File system scanner for files with configurable extensions.

[INPUT]: 无外部依赖（仅标准库 pathlib / stat / typing）
[OUTPUT]: scan_files(root_dirs, extensions, exclude_patterns, follow_symlinks, include_hidden)
[POS]: 文件发现层，按调用方传入的扩展名集合递归扫描目录，供 cli 使用
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
from pathlib import Path
import stat
from typing import Iterator

def scan_files(
    root_dirs: list[Path],
    extensions: set[str],
    exclude_patterns: list[str] | None = None,
    follow_symlinks: bool = False,
    include_hidden: bool = False
) -> Iterator[Path]:
    """
    Scan directories recursively for files with specified extensions.

    Args:
        root_dirs: List of directories to scan
        extensions: Set of file extensions to include (e.g., {'.mp4', '.jpg'})
        exclude_patterns: Directory name patterns to exclude
        follow_symlinks: Whether to follow symbolic links
        include_hidden: Whether to include hidden files/directories

    Yields:
        Absolute paths to matching files
    """
    exclude_patterns = exclude_patterns or []

    visited_inodes = set()
    visited_files: set[Path] = set()
    for root_dir in root_dirs:
        yield from _scan_directory(
            root_dir, extensions, exclude_patterns, follow_symlinks, include_hidden,
            visited_inodes, visited_files
        )

def _scan_directory(
    directory: Path,
    extensions: set[str],
    exclude_patterns: list[str],
    follow_symlinks: bool,
    include_hidden: bool,
    visited_inodes: set[tuple[int, int]],
    visited_files: set[Path]
) -> Iterator[Path]:
    """Recursively scan a single directory."""
    try:
        if directory.is_symlink() and not follow_symlinks:
            return

        directory_stat = directory.stat()
        inode = (directory_stat.st_dev, directory_stat.st_ino)
        if inode in visited_inodes:
            return
        visited_inodes.add(inode)

        for entry in directory.iterdir():
            # Skip hidden files/directories
            if not include_hidden and entry.name.startswith('.'):
                continue

            try:
                entry_stat = entry.lstat()
                if stat.S_ISLNK(entry_stat.st_mode):
                    if not follow_symlinks:
                        continue
                    entry_stat = entry.stat()

                if stat.S_ISDIR(entry_stat.st_mode):
                    if any(entry.name == pattern for pattern in exclude_patterns):
                        continue
                    yield from _scan_directory(
                        entry, extensions, exclude_patterns, follow_symlinks, include_hidden,
                        visited_inodes, visited_files
                    )
                elif stat.S_ISREG(entry_stat.st_mode) and entry.suffix.lower() in extensions:
                    resolved = entry.resolve()
                    if resolved not in visited_files:
                        visited_files.add(resolved)
                        yield resolved
            except (OSError, RuntimeError):
                # Entries may disappear or become inaccessible during a scan.
                continue
    except OSError:
        # Skip directories we can't access
        pass
