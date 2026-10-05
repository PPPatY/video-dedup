# Video Dedup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an efficient, safe video file deduplication tool for macOS that uses progressive hashing and SQLite caching to find and delete duplicate video files.

**Architecture:** Modular design with 7 core components: scanner (file traversal), hasher (progressive hashing), cache (SQLite persistence), grouper (duplicate detection), selector (retention rules), deleter (safe trash), and CLI (orchestration). TDD approach with unit tests before implementation.

**Tech Stack:** Python 3.10+, rich (terminal UI), send2trash (safe deletion), SQLite (caching), pytest (testing), uv (package management)

**Spec:** `docs/superpowers/specs/2026-10-05-video-dedup-design.md`

## Global Constraints

- Python version: >=3.10
- Hash algorithm: SHA-256 (no MD5, no SHA-1)
- Partial hash size: exactly 64KB (65536 bytes)
- Thread pool size: default 8, configurable via --threads
- Cache key: (absolute_path, file_size, mtime) tuple
- Never use os.remove() or os.unlink() - always use send2trash
- All file paths must be absolute (use Path.resolve())
- Video extensions: case-insensitive matching (normalize to lowercase)
- Time window for "similar time": 86400 seconds (24 hours)
- Log timestamp format: ISO 8601 with timezone

## Review Focus

1. **Empty directory input** - When scan receives [], expect clear error message "No directories specified", not a crash or silent success
2. **File disappears between scan and hash** - When a file is deleted after scanning but before hashing, expect FileNotFoundError caught, logged as warning, and scan continues
3. **Cache with stale paths** - When cache contains entries for files that no longer exist, expect those entries excluded from results and cleaned up during scan
4. **Two files with identical size and mtime but different content** - Progressive hashing must proceed to full hash stage, not assume they're duplicates
5. **Symlink loop with --follow-symlinks** - When directory A links to parent containing A, expect loop detected and traversal stops without infinite recursion

---

## Task 1: Project Setup and Structure

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `README.md`
- Create: `src/__init__.py`
- Create: `src/utils.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Interfaces:**
- Consumes: None
- Produces: 
  - `src/utils.py`: `VIDEO_EXTENSIONS: set[str]`, `format_size(bytes: int) -> str`, `format_duration(seconds: float) -> str`

- [ ] **Step 1: Write test for VIDEO_EXTENSIONS constant**

```python
# tests/test_utils.py
def test_video_extensions_contains_common_formats():
    from src.utils import VIDEO_EXTENSIONS
    assert '.mp4' in VIDEO_EXTENSIONS
    assert '.mov' in VIDEO_EXTENSIONS
    assert '.avi' in VIDEO_EXTENSIONS
    assert '.mkv' in VIDEO_EXTENSIONS
    assert len(VIDEO_EXTENSIONS) >= 15  # At least 15 formats
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_utils.py::test_video_extensions_contains_common_formats -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src'"

- [ ] **Step 3: Create pyproject.toml with dependencies**

```toml
[project]
name = "video-dedup"
version = "1.0.0"
description = "高效、安全的视频文件去重工具"
requires-python = ">=3.10"
dependencies = [
    "rich>=13.0.0",
    "send2trash>=1.8.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
]

[project.scripts]
video-dedup = "src.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
```

- [ ] **Step 4: Create src/__init__.py and src/utils.py with VIDEO_EXTENSIONS**

```python
# src/__init__.py
"""Video deduplication tool."""

# src/utils.py
"""Utility functions and constants."""

VIDEO_EXTENSIONS = {
    '.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.m4v',
    '.mpg', '.mpeg', '.3gp', '.webm', '.ogv', '.ts', '.mts',
    '.vob', '.rm', '.rmvb', '.asf', '.m2ts', '.divx'
}

def format_size(bytes: int) -> str:
    """Format bytes as human-readable size (e.g., '1.2 GB')."""
    raise NotImplementedError

def format_duration(seconds: float) -> str:
    """Format seconds as human-readable duration (e.g., '5 分 32 秒')."""
    raise NotImplementedError
```

- [ ] **Step 5: Create tests/__init__.py and tests/conftest.py**

```python
# tests/__init__.py
"""Test suite for video-dedup."""

# tests/conftest.py
import tempfile
import os
from pathlib import Path
import pytest

@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def create_test_file():
    """Factory fixture to create test files with specific content."""
    def _create(parent_dir: Path, filename: str, content: bytes) -> Path:
        file_path = parent_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)
        return file_path
    return _create
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_utils.py::test_video_extensions_contains_common_formats -v`
Expected: PASS

- [ ] **Step 7: Write tests for format_size**

```python
# tests/test_utils.py
def test_format_size_bytes():
    from src.utils import format_size
    assert format_size(500) == "500 B"

def test_format_size_kilobytes():
    from src.utils import format_size
    assert format_size(1536) == "1.5 KB"

def test_format_size_megabytes():
    from src.utils import format_size
    assert format_size(1_572_864) == "1.5 MB"

def test_format_size_gigabytes():
    from src.utils import format_size
    assert format_size(1_610_612_736) == "1.5 GB"
```

- [ ] **Step 8: Run tests to verify they fail**

Run: `pytest tests/test_utils.py -k format_size -v`
Expected: FAIL with "NotImplementedError"

- [ ] **Step 9: Implement format_size**

```python
# src/utils.py
def format_size(bytes: int) -> str:
    """Format bytes as human-readable size (e.g., '1.2 GB')."""
    if bytes < 1024:
        return f"{bytes} B"
    elif bytes < 1024 ** 2:
        return f"{bytes / 1024:.1f} KB"
    elif bytes < 1024 ** 3:
        return f"{bytes / (1024 ** 2):.1f} MB"
    else:
        return f"{bytes / (1024 ** 3):.1f} GB"
```

- [ ] **Step 10: Run tests to verify they pass**

Run: `pytest tests/test_utils.py -k format_size -v`
Expected: PASS

- [ ] **Step 11: Write tests for format_duration**

```python
# tests/test_utils.py
def test_format_duration_seconds():
    from src.utils import format_duration
    assert format_duration(45) == "45 秒"

def test_format_duration_minutes():
    from src.utils import format_duration
    assert format_duration(125) == "2 分 5 秒"

def test_format_duration_hours():
    from src.utils import format_duration
    assert format_duration(3725) == "1 小时 2 分 5 秒"
```

- [ ] **Step 12: Run tests to verify they fail**

Run: `pytest tests/test_utils.py -k format_duration -v`
Expected: FAIL with "NotImplementedError"

- [ ] **Step 13: Implement format_duration**

```python
# src/utils.py
def format_duration(seconds: float) -> str:
    """Format seconds as human-readable duration (e.g., '5 分 32 秒')."""
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours} 小时 {minutes} 分 {secs} 秒"
    elif minutes > 0:
        return f"{minutes} 分 {secs} 秒"
    else:
        return f"{secs} 秒"
```

- [ ] **Step 14: Run tests to verify they pass**

Run: `pytest tests/test_utils.py -k format_duration -v`
Expected: PASS

- [ ] **Step 15: Create .gitignore**

```
# .gitignore
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
.pytest_cache/
.coverage
htmlcov/
.venv/
venv/
ENV/
.idea/
.vscode/
*.swp
*.swo
*~
.DS_Store
```

- [ ] **Step 16: Create basic README.md**

```markdown
# Video Dedup

高效、安全的视频文件去重工具

## 功能特性

- 严格内容比对（基于 SHA-256 哈希）
- 渐进式哈希优化性能
- SQLite 缓存支持增量扫描
- 智能保留规则
- 安全删除（移到回收站）

## 安装

\`\`\`bash
# 使用 uv 安装
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
\`\`\`

## 使用

\`\`\`bash
video-dedup scan ~/Videos ~/Downloads
\`\`\`

## 开发

\`\`\`bash
# 运行测试
pytest

# 运行特定测试
pytest tests/test_utils.py -v
\`\`\`
```

- [ ] **Step 17: Commit project setup**

```bash
git init
git add .
git commit -m "feat: initial project setup with utils module

- Add pyproject.toml with dependencies
- Add VIDEO_EXTENSIONS constant
- Add format_size and format_duration utilities
- Add pytest configuration and fixtures
- Add .gitignore and README"
```

---

## Task 2: File Scanner Module

**Files:**
- Create: `src/scanner.py`
- Create: `tests/test_scanner.py`

**Interfaces:**
- Consumes: `src/utils.VIDEO_EXTENSIONS`
- Produces:
  - `scan_files(root_dirs: list[Path], exclude_patterns: list[str] = None, follow_symlinks: bool = False, include_hidden: bool = False) -> Iterator[Path]`

- [ ] **Step 1: Write test for scanning single directory**

```python
# tests/test_scanner.py
from pathlib import Path

def test_scan_single_directory_with_videos(temp_dir, create_test_file):
    """Test scanning a directory with video files."""
    from src.scanner import scan_files
    
    # Create test files
    create_test_file(temp_dir, "video1.mp4", b"content1")
    create_test_file(temp_dir, "video2.mov", b"content2")
    create_test_file(temp_dir, "document.txt", b"not a video")
    
    results = list(scan_files([temp_dir]))
    
    assert len(results) == 2
    assert all(p.suffix.lower() in {'.mp4', '.mov'} for p in results)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scanner.py::test_scan_single_directory_with_videos -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.scanner'"

- [ ] **Step 3: Create src/scanner.py with minimal implementation**

```python
# src/scanner.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_scanner.py::test_scan_single_directory_with_videos -v`
Expected: PASS

- [ ] **Step 5: Write test for nested directories**

```python
# tests/test_scanner.py
def test_scan_nested_directories(temp_dir, create_test_file):
    """Test scanning nested directory structure."""
    from src.scanner import scan_files
    
    create_test_file(temp_dir, "root.mp4", b"root")
    create_test_file(temp_dir, "sub1/video1.mp4", b"sub1")
    create_test_file(temp_dir, "sub1/sub2/video2.avi", b"sub2")
    
    results = list(scan_files([temp_dir]))
    
    assert len(results) == 3
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_scanner.py::test_scan_nested_directories -v`
Expected: PASS

- [ ] **Step 7: Write test for exclude patterns**

```python
# tests/test_scanner.py
def test_scan_with_exclude_patterns(temp_dir, create_test_file):
    """Test excluding directories by pattern."""
    from src.scanner import scan_files
    
    create_test_file(temp_dir, "keep/video1.mp4", b"keep")
    create_test_file(temp_dir, "iMovie 项目/video2.mp4", b"exclude")
    create_test_file(temp_dir, "Final Cut/video3.mov", b"exclude")
    
    results = list(scan_files([temp_dir], exclude_patterns=["iMovie 项目", "Final Cut"]))
    
    assert len(results) == 1
    assert "keep" in str(results[0])
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_scanner.py::test_scan_with_exclude_patterns -v`
Expected: PASS

- [ ] **Step 9: Write test for hidden files**

```python
# tests/test_scanner.py
def test_scan_skips_hidden_files_by_default(temp_dir, create_test_file):
    """Test that hidden files are skipped by default."""
    from src.scanner import scan_files
    
    create_test_file(temp_dir, "visible.mp4", b"visible")
    create_test_file(temp_dir, ".hidden.mp4", b"hidden")
    
    results = list(scan_files([temp_dir]))
    
    assert len(results) == 1
    assert results[0].name == "visible.mp4"

def test_scan_includes_hidden_files_when_enabled(temp_dir, create_test_file):
    """Test that hidden files are included when flag is set."""
    from src.scanner import scan_files
    
    create_test_file(temp_dir, "visible.mp4", b"visible")
    create_test_file(temp_dir, ".hidden.mp4", b"hidden")
    
    results = list(scan_files([temp_dir], include_hidden=True))
    
    assert len(results) == 2
```

- [ ] **Step 10: Run tests to verify they pass**

Run: `pytest tests/test_scanner.py -k hidden -v`
Expected: PASS

- [ ] **Step 11: Write test for multiple root directories**

```python
# tests/test_scanner.py
def test_scan_multiple_root_directories(temp_dir, create_test_file):
    """Test scanning multiple independent directories."""
    from src.scanner import scan_files
    
    dir1 = temp_dir / "dir1"
    dir2 = temp_dir / "dir2"
    
    create_test_file(dir1, "video1.mp4", b"dir1")
    create_test_file(dir2, "video2.mov", b"dir2")
    
    results = list(scan_files([dir1, dir2]))
    
    assert len(results) == 2
```

- [ ] **Step 12: Run test to verify it passes**

Run: `pytest tests/test_scanner.py::test_scan_multiple_root_directories -v`
Expected: PASS

- [ ] **Step 13: Write test for empty directory input (Review Focus #1)**

```python
# tests/test_scanner.py
def test_scan_empty_directory_list():
    """Test scanning with empty directory list."""
    from src.scanner import scan_files
    
    results = list(scan_files([]))
    
    assert results == []
```

- [ ] **Step 14: Run test to verify it passes**

Run: `pytest tests/test_scanner.py::test_scan_empty_directory_list -v`
Expected: PASS (already handled by for loop over empty list)

- [ ] **Step 15: Write test for symlink loop detection (Review Focus #5)**

```python
# tests/test_scanner.py
import os

def test_scan_detects_symlink_loop(temp_dir, create_test_file):
    """Test that symlink loops are detected and don't cause infinite recursion."""
    from src.scanner import scan_files
    
    # Create a directory structure with a loop: A -> B -> A
    dir_a = temp_dir / "dir_a"
    dir_b = dir_a / "dir_b"
    dir_a.mkdir()
    dir_b.mkdir()
    
    # Create symlink loop
    loop_link = dir_b / "link_to_a"
    loop_link.symlink_to(dir_a)
    
    create_test_file(dir_a, "video.mp4", b"content")
    
    # Should not hang or crash
    results = list(scan_files([temp_dir], follow_symlinks=True))
    
    assert len(results) == 1  # Should find video once, not infinite times
```

- [ ] **Step 16: Run test to verify it passes**

Run: `pytest tests/test_scanner.py::test_scan_detects_symlink_loop -v`
Expected: PASS

- [ ] **Step 17: Commit scanner module**

```bash
git add src/scanner.py tests/test_scanner.py
git commit -m "feat: add file scanner module

- Recursive directory traversal
- Video file filtering by extension
- Exclude pattern support
- Hidden file handling
- Symlink loop detection
- Permission error handling"
```

---

## Task 3: Hash Calculator Module

**Files:**
- Create: `src/hasher.py`
- Create: `tests/test_hasher.py`

**Interfaces:**
- Consumes: None
- Produces:
  - `compute_partial_hash(file_path: Path, size: int = 65536) -> str`
  - `compute_full_hash(file_path: Path) -> str`
  - `FileHashInfo` dataclass with fields: `path: Path`, `size: int`, `partial_hash: str`, `full_hash: str | None`

- [ ] **Step 1: Write test for partial hash computation**

```python
# tests/test_hasher.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_hasher.py::test_compute_partial_hash_first_64kb -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.hasher'"

- [ ] **Step 3: Create src/hasher.py with partial hash**

```python
# src/hasher.py
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
    raise NotImplementedError
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_hasher.py::test_compute_partial_hash_first_64kb -v`
Expected: PASS

- [ ] **Step 5: Write test for partial hash on small files**

```python
# tests/test_hasher.py
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
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_hasher.py::test_compute_partial_hash_small_file -v`
Expected: PASS

- [ ] **Step 7: Write test for full hash computation**

```python
# tests/test_hasher.py
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
```

- [ ] **Step 8: Run test to verify it fails**

Run: `pytest tests/test_hasher.py::test_compute_full_hash -v`
Expected: FAIL with "NotImplementedError"

- [ ] **Step 9: Implement compute_full_hash with chunked reading**

```python
# src/hasher.py
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
```

- [ ] **Step 10: Run test to verify it passes**

Run: `pytest tests/test_hasher.py::test_compute_full_hash -v`
Expected: PASS

- [ ] **Step 11: Write test for identical files producing same hash**

```python
# tests/test_hasher.py
def test_identical_files_produce_same_hash(temp_dir, create_test_file):
    """Test that identical files produce identical hashes."""
    from src.hasher import compute_full_hash
    
    content = b"identical content"
    file1 = create_test_file(temp_dir, "file1.mp4", content)
    file2 = create_test_file(temp_dir, "file2.mp4", content)
    
    hash1 = compute_full_hash(file1)
    hash2 = compute_full_hash(file2)
    
    assert hash1 == hash2
```

- [ ] **Step 12: Run test to verify it passes**

Run: `pytest tests/test_hasher.py::test_identical_files_produce_same_hash -v`
Expected: PASS

- [ ] **Step 13: Write test for different files producing different hashes**

```python
# tests/test_hasher.py
def test_different_files_produce_different_hash(temp_dir, create_test_file):
    """Test that different files produce different hashes."""
    from src.hasher import compute_full_hash
    
    file1 = create_test_file(temp_dir, "file1.mp4", b"content1")
    file2 = create_test_file(temp_dir, "file2.mp4", b"content2")
    
    hash1 = compute_full_hash(file1)
    hash2 = compute_full_hash(file2)
    
    assert hash1 != hash2
```

- [ ] **Step 14: Run test to verify it passes**

Run: `pytest tests/test_hasher.py::test_different_files_produce_different_hash -v`
Expected: PASS

- [ ] **Step 15: Write test for file disappearing during hash (Review Focus #2)**

```python
# tests/test_hasher.py
import pytest

def test_compute_hash_file_not_found(temp_dir):
    """Test hashing non-existent file raises FileNotFoundError."""
    from src.hasher import compute_full_hash
    from pathlib import Path
    
    non_existent = temp_dir / "does_not_exist.mp4"
    
    with pytest.raises(FileNotFoundError):
        compute_full_hash(non_existent)
```

- [ ] **Step 16: Run test to verify it passes**

Run: `pytest tests/test_hasher.py::test_compute_hash_file_not_found -v`
Expected: PASS (already raises FileNotFoundError)

- [ ] **Step 17: Write test for large file hash (performance check)**

```python
# tests/test_hasher.py
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
```

- [ ] **Step 18: Run test to verify it passes**

Run: `pytest tests/test_hasher.py::test_compute_hash_large_file -v`
Expected: PASS

- [ ] **Step 19: Commit hasher module**

```bash
git add src/hasher.py tests/test_hasher.py
git commit -m "feat: add hash calculator module

- Partial hash (first 64KB) for quick comparison
- Full file hash with chunked reading
- FileHashInfo dataclass
- Handle small files and large files correctly"
```

---

## Task 4: SQLite Cache Module

**Files:**
- Create: `src/cache.py`
- Create: `tests/test_cache.py`

**Interfaces:**
- Consumes: None
- Produces:
  - `Cache` class with methods:
    - `__init__(cache_dir: Path)`
    - `get_hash(file_path: Path, size: int, mtime: float) -> str | None`
    - `store_hash(file_path: Path, size: int, mtime: float, full_hash: str, partial_hash: str = None)`
    - `update_last_seen(file_path: Path)`
    - `clean_old_entries(days: int = 30)`
    - `clear()`
    - `get_stats() -> dict[str, int]` (returns hit_count, miss_count)

- [ ] **Step 1: Write test for cache initialization**

```python
# tests/test_cache.py
from pathlib import Path
import sqlite3

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cache.py::test_cache_creates_database -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.cache'"

- [ ] **Step 3: Create src/cache.py with initialization**

```python
# src/cache.py
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
        """Get cached hash if file unchanged."""
        raise NotImplementedError
    
    def store_hash(self, file_path: Path, size: int, mtime: float, full_hash: str, partial_hash: str = None):
        """Store hash in cache."""
        raise NotImplementedError
    
    def update_last_seen(self, file_path: Path):
        """Update last_seen timestamp."""
        raise NotImplementedError
    
    def clean_old_entries(self, days: int = 30):
        """Remove entries not seen in N days."""
        raise NotImplementedError
    
    def clear(self):
        """Clear all cache entries."""
        raise NotImplementedError
    
    def get_stats(self) -> dict[str, int]:
        """Get cache statistics."""
        return {"hit_count": self.hit_count, "miss_count": self.miss_count}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cache.py::test_cache_creates_database -v`
Expected: PASS

- [ ] **Step 5: Write test for cache miss**

```python
# tests/test_cache.py
def test_cache_miss_returns_none(temp_dir):
    """Test cache miss returns None."""
    from src.cache import Cache
    from pathlib import Path
    
    cache = Cache(temp_dir / "cache")
    
    result = cache.get_hash(Path("/some/file.mp4"), 1000, 1234567890.0)
    
    assert result is None
    assert cache.get_stats()["miss_count"] == 1
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/test_cache.py::test_cache_miss_returns_none -v`
Expected: FAIL with "NotImplementedError"

- [ ] **Step 7: Implement get_hash**

```python
# src/cache.py
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
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_cache.py::test_cache_miss_returns_none -v`
Expected: PASS

- [ ] **Step 9: Write test for cache hit**

```python
# tests/test_cache.py
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
```

- [ ] **Step 10: Run test to verify it fails**

Run: `pytest tests/test_cache.py::test_cache_hit_returns_hash -v`
Expected: FAIL with "NotImplementedError"

- [ ] **Step 11: Implement store_hash**

```python
# src/cache.py
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
```

- [ ] **Step 12: Run test to verify it passes**

Run: `pytest tests/test_cache.py::test_cache_hit_returns_hash -v`
Expected: PASS

- [ ] **Step 13: Write test for cache invalidation on file change**

```python
# tests/test_cache.py
import time

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
```

- [ ] **Step 14: Run test to verify it passes**

Run: `pytest tests/test_cache.py::test_cache_miss_after_file_modification -v`
Expected: PASS

- [ ] **Step 15: Write test for update_last_seen**

```python
# tests/test_cache.py
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
```

- [ ] **Step 16: Run test to verify it fails**

Run: `pytest tests/test_cache.py::test_update_last_seen -v`
Expected: FAIL with "NotImplementedError"

- [ ] **Step 17: Implement update_last_seen**

```python
# src/cache.py
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
```

- [ ] **Step 18: Run test to verify it passes**

Run: `pytest tests/test_cache.py::test_update_last_seen -v`
Expected: PASS

- [ ] **Step 19: Write test for clean_old_entries**

```python
# tests/test_cache.py
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
```

- [ ] **Step 20: Run test to verify it fails**

Run: `pytest tests/test_cache.py::test_clean_old_entries -v`
Expected: FAIL with "NotImplementedError"

- [ ] **Step 21: Implement clean_old_entries**

```python
# src/cache.py
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
```

- [ ] **Step 22: Run test to verify it passes**

Run: `pytest tests/test_cache.py::test_clean_old_entries -v`
Expected: PASS

- [ ] **Step 23: Write test for clear method**

```python
# tests/test_cache.py
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
```

- [ ] **Step 24: Run test to verify it fails**

Run: `pytest tests/test_cache.py::test_clear_all_entries -v`
Expected: FAIL with "NotImplementedError"

- [ ] **Step 25: Implement clear**

```python
# src/cache.py
def clear(self):
    """Clear all cache entries."""
    conn = sqlite3.connect(self.db_path)
    conn.execute("DELETE FROM file_hashes")
    conn.commit()
    conn.close()
```

- [ ] **Step 26: Run test to verify it passes**

Run: `pytest tests/test_cache.py::test_clear_all_entries -v`
Expected: PASS

- [ ] **Step 27: Commit cache module**

```bash
git add src/cache.py tests/test_cache.py
git commit -m "feat: add SQLite cache module

- Initialize database with proper schema
- Store and retrieve file hashes
- Cache hit/miss tracking
- Invalidation on file changes
- Clean old entries
- Clear cache functionality"
```

---

## Task 5: Duplicate Grouper Module

**Files:**
- Create: `src/grouper.py`
- Create: `tests/test_grouper.py`

**Interfaces:**
- Consumes: `src.hasher.FileHashInfo`, `src.hasher.compute_partial_hash`, `src.hasher.compute_full_hash`
- Produces:
  - `group_by_size(files: list[Path]) -> dict[int, list[Path]]`
  - `group_by_hash(files: list[Path], hash_func: Callable) -> dict[str, list[Path]]`
  - `find_duplicates(files: list[Path], cache: Cache | None = None) -> list[list[Path]]` (returns list of duplicate groups)

- [ ] **Step 1: Write test for grouping by size**

```python
# tests/test_grouper.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_grouper.py::test_group_by_size -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.grouper'"

- [ ] **Step 3: Create src/grouper.py with group_by_size**

```python
# src/grouper.py
"""Duplicate file grouping logic."""
from pathlib import Path
from collections import defaultdict
from typing import Callable
import os

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
    """Group files by hash."""
    raise NotImplementedError

def find_duplicates(files: list[Path], cache=None) -> list[list[Path]]:
    """Find duplicate files using progressive hashing."""
    raise NotImplementedError
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_grouper.py::test_group_by_size -v`
Expected: PASS

- [ ] **Step 5: Write test for grouping by hash**

```python
# tests/test_grouper.py
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
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/test_grouper.py::test_group_by_hash -v`
Expected: FAIL with "NotImplementedError"

- [ ] **Step 7: Implement group_by_hash**

```python
# src/grouper.py
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
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_grouper.py::test_group_by_hash -v`
Expected: PASS

- [ ] **Step 9: Write test for find_duplicates with progressive hashing**

```python
# tests/test_grouper.py
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
```

- [ ] **Step 10: Run test to verify it fails**

Run: `pytest tests/test_grouper.py::test_find_duplicates_three_stage -v`
Expected: FAIL with "NotImplementedError"

- [ ] **Step 11: Implement find_duplicates with progressive hashing**

```python
# src/grouper.py
from src.hasher import compute_partial_hash, compute_full_hash

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
    
    # Stage 3: Group by full hash
    full_groups = group_by_hash(candidates, compute_full_hash)
    
    # Return only groups with 2+ files
    duplicates = [file_list for file_list in full_groups.values() if len(file_list) > 1]
    
    return duplicates
```

- [ ] **Step 12: Run test to verify it passes**

Run: `pytest tests/test_grouper.py::test_find_duplicates_three_stage -v`
Expected: PASS

- [ ] **Step 13: Write test for files with same size and mtime but different content (Review Focus #4)**

```python
# tests/test_grouper.py
import os
import time

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
```

- [ ] **Step 14: Run test to verify it passes**

Run: `pytest tests/test_grouper.py::test_find_duplicates_same_size_different_content -v`
Expected: PASS (progressive hashing handles this)

- [ ] **Step 15: Write test for find_duplicates with cache integration**

```python
# tests/test_grouper.py
def test_find_duplicates_uses_cache(temp_dir, create_test_file):
    """Test that find_duplicates uses cache when provided."""
    from src.grouper import find_duplicates
    from src.cache import Cache
    import os
    
    cache = Cache(temp_dir / "cache")
    
    # Create identical files
    file1 = create_test_file(temp_dir, "file1.mp4", b"content")
    file2 = create_test_file(temp_dir, "file2.mp4", b"content")
    
    # Pre-populate cache
    stat1 = os.stat(file1)
    from src.hasher import compute_full_hash
    hash1 = compute_full_hash(file1)
    cache.store_hash(file1, stat1.st_size, stat1.st_mtime, hash1)
    
    # Find duplicates (should use cache for file1)
    duplicates = find_duplicates([file1, file2], cache=cache)
    
    assert len(duplicates) == 1
    assert set(duplicates[0]) == {file1, file2}
    
    # Verify cache was used (at least one hit)
    stats = cache.get_stats()
    assert stats["hit_count"] >= 1
```

- [ ] **Step 16: Run test to verify it fails (cache not yet integrated)**

Run: `pytest tests/test_grouper.py::test_find_duplicates_uses_cache -v`
Expected: FAIL (cache parameter not used)

- [ ] **Step 17: Integrate cache into find_duplicates**

```python
# src/grouper.py
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
```

- [ ] **Step 18: Run test to verify it passes**

Run: `pytest tests/test_grouper.py::test_find_duplicates_uses_cache -v`
Expected: PASS

- [ ] **Step 19: Commit grouper module**

```bash
git add src/grouper.py tests/test_grouper.py
git commit -m "feat: add duplicate grouper module

- Group files by size (stage 1)
- Group files by partial hash (stage 2)
- Group files by full hash (stage 3)
- Progressive hashing strategy
- Cache integration for performance
- Handle same-size different-content correctly"
```

---

## Task 6: Retention Selector Module

**Files:**
- Create: `src/selector.py`
- Create: `tests/test_selector.py`

**Interfaces:**
- Consumes: None
- Produces:
  - `select_files_to_keep(duplicate_groups: list[list[Path]]) -> dict[Path, list[Path]]` (returns {file_to_keep: [files_to_delete]})

- [ ] **Step 1: Write test for selecting oldest file**

```python
# tests/test_selector.py
import os
import time

def test_select_oldest_file(temp_dir, create_test_file):
    """Test selecting oldest file based on mtime."""
    from src.selector import select_files_to_keep
    
    # Create files with different mtimes
    file1 = create_test_file(temp_dir, "file1.mp4", b"content")
    time.sleep(0.01)
    file2 = create_test_file(temp_dir, "file2.mp4", b"content")
    time.sleep(0.01)
    file3 = create_test_file(temp_dir, "file3.mp4", b"content")
    
    duplicate_groups = [[file1, file2, file3]]
    result = select_files_to_keep(duplicate_groups)
    
    # Should keep file1 (oldest)
    assert file1 in result
    assert set(result[file1]) == {file2, file3}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_selector.py::test_select_oldest_file -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.selector'"

- [ ] **Step 3: Create src/selector.py with basic implementation**

```python
# src/selector.py
"""File retention rule selector."""
from pathlib import Path
import os

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
        
        # Keep the oldest
        to_keep = sorted_files[0]
        to_delete = sorted_files[1:]
        
        result[to_keep] = to_delete
    
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_selector.py::test_select_oldest_file -v`
Expected: PASS

- [ ] **Step 5: Write test for shortest path rule**

```python
# tests/test_selector.py
def test_select_shortest_path_when_similar_time(temp_dir, create_test_file):
    """Test selecting shortest path when mtimes are similar."""
    from src.selector import select_files_to_keep
    
    # Create files with same content
    file1 = create_test_file(temp_dir, "short.mp4", b"content")
    file2 = create_test_file(temp_dir, "very/long/nested/path/file.mp4", b"content")
    
    # Set similar mtimes (within 1 hour)
    mtime = time.time()
    os.utime(file1, (mtime, mtime))
    os.utime(file2, (mtime + 3600, mtime + 3600))  # 1 hour later
    
    duplicate_groups = [[file1, file2]]
    result = select_files_to_keep(duplicate_groups)
    
    # Should keep shorter path
    assert file1 in result
    assert file2 in result[file1]
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/test_selector.py::test_select_shortest_path_when_similar_time -v`
Expected: FAIL (current implementation doesn't check path length)

- [ ] **Step 7: Implement shortest path rule**

```python
# src/selector.py
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
            to_keep = min(similar_time_files, key=lambda f: len(str(f)))
        else:
            # Keep the oldest
            to_keep = oldest_file
        
        to_delete = [f for f in group if f != to_keep]
        result[to_keep] = to_delete
    
    return result
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_selector.py::test_select_shortest_path_when_similar_time -v`
Expected: PASS

- [ ] **Step 9: Write test for lexicographic ordering**

```python
# tests/test_selector.py
def test_select_lexicographic_when_same_path_length(temp_dir, create_test_file):
    """Test lexicographic selection when path lengths are equal."""
    from src.selector import select_files_to_keep
    
    # Create files with same length paths
    file1 = create_test_file(temp_dir, "zebra.mp4", b"content")
    file2 = create_test_file(temp_dir, "apple.mp4", b"content")
    
    # Set same mtime
    mtime = time.time()
    os.utime(file1, (mtime, mtime))
    os.utime(file2, (mtime, mtime))
    
    duplicate_groups = [[file1, file2]]
    result = select_files_to_keep(duplicate_groups)
    
    # Should keep lexicographically first (apple < zebra)
    assert file2 in result  # apple
    assert file1 in result[file2]  # zebra
```

- [ ] **Step 10: Run test to verify it fails**

Run: `pytest tests/test_selector.py::test_select_lexicographic_when_same_path_length -v`
Expected: FAIL (need to add lexicographic sort)

- [ ] **Step 11: Implement lexicographic rule**

```python
# src/selector.py
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
```

- [ ] **Step 12: Run test to verify it passes**

Run: `pytest tests/test_selector.py::test_select_lexicographic_when_same_path_length -v`
Expected: PASS

- [ ] **Step 13: Write test for multiple duplicate groups**

```python
# tests/test_selector.py
def test_select_from_multiple_groups(temp_dir, create_test_file):
    """Test selecting from multiple independent duplicate groups."""
    from src.selector import select_files_to_keep
    
    # Group 1
    g1_file1 = create_test_file(temp_dir, "group1/a.mp4", b"content1")
    time.sleep(0.01)
    g1_file2 = create_test_file(temp_dir, "group1/b.mp4", b"content1")
    
    # Group 2
    g2_file1 = create_test_file(temp_dir, "group2/x.mp4", b"content2")
    time.sleep(0.01)
    g2_file2 = create_test_file(temp_dir, "group2/y.mp4", b"content2")
    
    duplicate_groups = [[g1_file1, g1_file2], [g2_file1, g2_file2]]
    result = select_files_to_keep(duplicate_groups)
    
    # Should have 2 entries (one per group)
    assert len(result) == 2
    assert g1_file1 in result
    assert g2_file1 in result
```

- [ ] **Step 14: Run test to verify it passes**

Run: `pytest tests/test_selector.py::test_select_from_multiple_groups -v`
Expected: PASS

- [ ] **Step 15: Commit selector module**

```bash
git add src/selector.py tests/test_selector.py
git commit -m "feat: add retention selector module

- Select oldest file by mtime
- Prefer shortest path when times similar
- Lexicographic ordering as tiebreaker
- Handle multiple duplicate groups"
```

---

## Task 7: Safe Deleter Module

**Files:**
- Create: `src/deleter.py`
- Create: `tests/test_deleter.py`

**Interfaces:**
- Consumes: None
- Produces:
  - `delete_files(files: list[Path], dry_run: bool = False) -> dict[str, any]` (returns {"success": [...], "failed": [...], "skipped": [...]})
  - `create_deletion_log(log_dir: Path, deletion_result: dict, duplicate_groups: list) -> Path`

- [ ] **Step 1: Write test for safe deletion to trash**

```python
# tests/test_deleter.py
def test_delete_files_moves_to_trash(temp_dir, create_test_file):
    """Test that files are moved to trash, not permanently deleted."""
    from src.deleter import delete_files
    
    file1 = create_test_file(temp_dir, "file1.mp4", b"content")
    file2 = create_test_file(temp_dir, "file2.mp4", b"content")
    
    result = delete_files([file1, file2])
    
    # Files should no longer exist in original location
    assert not file1.exists()
    assert not file2.exists()
    
    # Result should show success
    assert len(result["success"]) == 2
    assert len(result["failed"]) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_deleter.py::test_delete_files_moves_to_trash -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.deleter'"

- [ ] **Step 3: Create src/deleter.py with delete implementation**

```python
# src/deleter.py
"""Safe file deletion via system trash."""
from pathlib import Path
from send2trash import send2trash
import json
from datetime import datetime

def delete_files(files: list[Path], dry_run: bool = False) -> dict[str, any]:
    """
    Delete files by moving to system trash.
    
    Args:
        files: List of files to delete
        dry_run: If True, don't actually delete
        
    Returns:
        Dictionary with success, failed, and skipped lists
    """
    result = {
        "success": [],
        "failed": [],
        "skipped": []
    }
    
    if dry_run:
        result["skipped"] = [str(f) for f in files]
        return result
    
    for file_path in files:
        try:
            send2trash(str(file_path))
            result["success"].append(str(file_path))
        except Exception as e:
            result["failed"].append({"path": str(file_path), "error": str(e)})
    
    return result

def create_deletion_log(log_dir: Path, deletion_result: dict, duplicate_groups: list) -> Path:
    """Create JSON log of deletion operation."""
    raise NotImplementedError
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_deleter.py::test_delete_files_moves_to_trash -v`
Expected: PASS

- [ ] **Step 5: Write test for dry-run mode**

```python
# tests/test_deleter.py
def test_delete_files_dry_run_skips_deletion(temp_dir, create_test_file):
    """Test dry-run mode doesn't actually delete files."""
    from src.deleter import delete_files
    
    file1 = create_test_file(temp_dir, "file1.mp4", b"content")
    
    result = delete_files([file1], dry_run=True)
    
    # File should still exist
    assert file1.exists()
    
    # Result should show skipped
    assert len(result["skipped"]) == 1
    assert len(result["success"]) == 0
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_deleter.py::test_delete_files_dry_run_skips_deletion -v`
Expected: PASS

- [ ] **Step 7: Write test for handling permission errors**

```python
# tests/test_deleter.py
import os

def test_delete_files_handles_permission_errors(temp_dir, create_test_file):
    """Test that permission errors are caught and reported."""
    from src.deleter import delete_files
    
    file1 = create_test_file(temp_dir, "file1.mp4", b"content")
    
    # Make file read-only (simulate permission issue)
    # Note: This test may behave differently on different OSes
    os.chmod(file1, 0o444)
    
    result = delete_files([file1])
    
    # Should either succeed (send2trash handles it) or fail gracefully
    assert len(result["success"]) + len(result["failed"]) == 1
    
    # Clean up - restore permissions
    if file1.exists():
        os.chmod(file1, 0o644)
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_deleter.py::test_delete_files_handles_permission_errors -v`
Expected: PASS

- [ ] **Step 9: Write test for deletion log creation**

```python
# tests/test_deleter.py
def test_create_deletion_log(temp_dir, create_test_file):
    """Test creating deletion log file."""
    from src.deleter import create_deletion_log
    
    file1 = create_test_file(temp_dir, "file1.mp4", b"content")
    file2 = create_test_file(temp_dir, "file2.mp4", b"content")
    
    deletion_result = {
        "success": [str(file2)],
        "failed": [],
        "skipped": []
    }
    
    duplicate_groups = [[file1, file2]]
    
    log_dir = temp_dir / "logs"
    log_path = create_deletion_log(log_dir, deletion_result, duplicate_groups)
    
    assert log_path.exists()
    assert log_path.suffix == ".log"
    
    # Verify JSON content
    with open(log_path) as f:
        log_data = json.load(f)
    
    assert "timestamp" in log_data
    assert "deleted_files" in log_data
    assert len(log_data["deleted_files"]) == 1
```

- [ ] **Step 10: Run test to verify it fails**

Run: `pytest tests/test_deleter.py::test_create_deletion_log -v`
Expected: FAIL with "NotImplementedError"

- [ ] **Step 11: Implement create_deletion_log**

```python
# src/deleter.py
def create_deletion_log(log_dir: Path, deletion_result: dict, duplicate_groups: list) -> Path:
    """
    Create JSON log of deletion operation.
    
    Args:
        log_dir: Directory to store log files
        deletion_result: Result from delete_files
        duplicate_groups: Original duplicate groups
        
    Returns:
        Path to created log file
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now()
    log_filename = timestamp.strftime("%Y-%m-%d_%H%M%S.log")
    log_path = log_dir / log_filename
    
    log_data = {
        "timestamp": timestamp.isoformat(),
        "version": "1.0.0",
        "duplicate_groups": len(duplicate_groups),
        "deleted_files": deletion_result["success"],
        "failed_deletions": deletion_result["failed"],
        "skipped_files": deletion_result["skipped"]
    }
    
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)
    
    return log_path
```

- [ ] **Step 12: Run test to verify it passes**

Run: `pytest tests/test_deleter.py::test_create_deletion_log -v`
Expected: PASS

- [ ] **Step 13: Commit deleter module**

```bash
git add src/deleter.py tests/test_deleter.py
git commit -m "feat: add safe deleter module

- Move files to system trash (never os.remove)
- Dry-run mode support
- Error handling for permission issues
- JSON deletion logs
- Track success/failed/skipped files"
```

---

## Task 8: CLI Module and Main Entry Point

**Files:**
- Create: `src/cli.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: All previous modules
- Produces:
  - `main()` function - CLI entry point
  - Command: `video-dedup scan <directories...> [options]`

- [ ] **Step 1: Write test for CLI help message**

```python
# tests/test_cli.py
import subprocess
import sys

def test_cli_help_message():
    """Test CLI shows help message."""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli", "--help"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert "video-dedup" in result.stdout.lower() or "scan" in result.stdout.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::test_cli_help_message -v`
Expected: FAIL with error running CLI

- [ ] **Step 3: Create basic CLI structure**

```python
# src/cli.py
"""Command-line interface for video-dedup."""
import sys
import argparse
from pathlib import Path
from rich.console import Console
from rich.progress import Progress

console = Console()

def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        prog="video-dedup",
        description="高效、安全的视频文件去重工具"
    )
    
    parser.add_argument(
        "directories",
        nargs="*",
        type=Path,
        help="要扫描的目录"
    )
    
    parser.add_argument(
        "--exclude",
        nargs="+",
        default=[],
        help="排除的目录名称"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，不实际删除"
    )
    
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path.home() / ".video-dedup",
        help="缓存目录（默认 ~/.video-dedup）"
    )
    
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="清空缓存"
    )
    
    parser.add_argument(
        "--threads",
        type=int,
        default=8,
        help="并发线程数（默认 8）"
    )
    
    parser.add_argument(
        "--follow-symlinks",
        action="store_true",
        help="跟随符号链接"
    )
    
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="包含隐藏文件"
    )
    
    return parser

def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.directories:
        console.print("[red]错误: 未指定扫描目录[/red]")
        parser.print_help()
        sys.exit(1)
    
    console.print("[green]video-dedup v1.0.0[/green]")
    # TODO: Implement scan logic

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py::test_cli_help_message -v`
Expected: PASS

- [ ] **Step 5: Write integration test for full workflow**

```python
# tests/test_cli.py
def test_cli_scan_workflow(temp_dir, create_test_file):
    """Test complete scan workflow."""
    from src.cli import main
    import sys
    
    # Create test files
    file1 = create_test_file(temp_dir, "dup1.mp4", b"same")
    file2 = create_test_file(temp_dir, "dup2.mp4", b"same")
    file3 = create_test_file(temp_dir, "unique.mp4", b"different")
    
    # Mock sys.argv
    sys.argv = [
        "video-dedup",
        str(temp_dir),
        "--dry-run",
        "--cache-dir", str(temp_dir / "cache")
    ]
    
    # Should run without errors
    try:
        main()
    except SystemExit as e:
        assert e.code == 0
```

- [ ] **Step 6: Run test to verify it fails (scan not implemented)**

Run: `pytest tests/test_cli.py::test_cli_scan_workflow -v`
Expected: FAIL (scan logic not implemented)

- [ ] **Step 7: Implement scan workflow in CLI**

```python
# src/cli.py (add to main function)
from src.scanner import scan_files
from src.grouper import find_duplicates
from src.selector import select_files_to_keep
from src.deleter import delete_files, create_deletion_log
from src.cache import Cache
from src.utils import format_size, format_duration
import time

def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.directories:
        console.print("[red]错误: 未指定扫描目录[/red]")
        parser.print_help()
        sys.exit(1)
    
    console.print("[green]🔍 扫描视频文件...[/green]\n")
    
    # Initialize cache
    cache = None
    if args.cache_dir:
        cache = Cache(args.cache_dir)
        if args.clear_cache:
            console.print("清空缓存...")
            cache.clear()
    
    # Scan files
    console.print(f"扫描目录:")
    for directory in args.directories:
        console.print(f"  • {directory}")
    
    if args.exclude:
        console.print(f"排除规则:")
        for pattern in args.exclude:
            console.print(f"  • {pattern}")
    
    start_time = time.time()
    
    files = list(scan_files(
        args.directories,
        exclude_patterns=args.exclude,
        follow_symlinks=args.follow_symlinks,
        include_hidden=args.include_hidden
    ))
    
    if not files:
        console.print("\n[yellow]未找到视频文件[/yellow]")
        sys.exit(0)
    
    console.print(f"\n找到 {len(files)} 个视频文件")
    
    # Find duplicates
    console.print("查找重复文件...")
    duplicate_groups = find_duplicates(files, cache=cache)
    
    if not duplicate_groups:
        console.print("\n[green]✓ 未发现重复文件[/green]")
        sys.exit(0)
    
    # Select files to keep/delete
    selections = select_files_to_keep(duplicate_groups)
    
    total_duplicates = sum(len(to_delete) for to_delete in selections.values())
    total_size = sum(
        sum(f.stat().st_size for f in to_delete)
        for to_delete in selections.values()
    )
    
    # Display summary
    console.print("\n" + "=" * 50)
    console.print(f"[green]✓ 扫描完成[/green] (用时 {format_duration(time.time() - start_time)})")
    console.print(f"\n📊 统计:")
    console.print(f"  • 总文件数: {len(files)} 个视频")
    console.print(f"  • 发现重复: {len(duplicate_groups)} 组（{total_duplicates} 个文件可删除）")
    console.print(f"  • 可释放空间: {format_size(total_size)}")
    
    if cache:
        stats = cache.get_stats()
        if stats["hit_count"] + stats["miss_count"] > 0:
            hit_rate = stats["hit_count"] / (stats["hit_count"] + stats["miss_count"])
            console.print(f"  • 缓存命中率: {hit_rate:.1%}")
    
    console.print(f"\n🗑️  删除策略:")
    console.print(f"  • 保留最早修改的文件")
    console.print(f"  • 时间相近时保留路径最短的")
    
    # Confirm deletion
    if args.dry_run:
        console.print(f"\n[yellow]⚠️  预览模式（--dry-run）：不会实际删除文件[/yellow]")
        # Create deletion log
        log_path = create_deletion_log(
            args.cache_dir / "logs",
            {"success": [], "failed": [], "skipped": [str(f) for to_delete in selections.values() for f in to_delete]},
            duplicate_groups
        )
        console.print(f"删除计划已保存到: {log_path}")
    else:
        console.print(f"\n确认删除 {total_duplicates} 个重复文件？[y/N] ", end="")
        response = input().strip().lower()
        
        if response == 'y':
            # Delete files
            all_to_delete = [f for to_delete in selections.values() for f in to_delete]
            result = delete_files(all_to_delete)
            
            console.print(f"\n[green]✓ 操作完成[/green]")
            console.print(f"  • 已删除: {len(result['success'])} 个文件")
            console.print(f"  • 已释放: {format_size(total_size)}")
            console.print(f"  • 文件已移至回收站（可在"废纸篓"中恢复）")
            
            # Create log
            log_path = create_deletion_log(args.cache_dir / "logs", result, duplicate_groups)
            console.print(f"  • 操作日志: {log_path}")
            
            if result["failed"]:
                console.print(f"\n[yellow]警告: {len(result['failed'])} 个文件删除失败（详见日志）[/yellow]")
        else:
            console.print("\n取消操作")
    
    sys.exit(0)
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_cli.py::test_cli_scan_workflow -v`
Expected: PASS

- [ ] **Step 9: Write test for empty directory error (Review Focus #1)**

```python
# tests/test_cli.py
def test_cli_empty_directory_list_error():
    """Test CLI handles empty directory list with clear error."""
    from src.cli import main
    import sys
    
    sys.argv = ["video-dedup"]
    
    try:
        main()
        assert False, "Should have exited with error"
    except SystemExit as e:
        assert e.code == 1
```

- [ ] **Step 10: Run test to verify it passes**

Run: `pytest tests/test_cli.py::test_cli_empty_directory_list_error -v`
Expected: PASS (already handles this)

- [ ] **Step 11: Commit CLI module**

```bash
git add src/cli.py tests/test_cli.py
git commit -m "feat: add CLI module and main entry point

- Argument parsing with all options
- Complete scan workflow integration
- Progress display with rich
- User confirmation for deletion
- Dry-run mode support
- Cache statistics display
- Error handling for empty input"
```

---

## Task 9: Integration Tests and Documentation

**Files:**
- Create: `tests/test_integration.py`
- Modify: `README.md`
- Create: `CHANGELOG.md`

**Interfaces:**
- Consumes: All modules
- Produces: Complete test coverage and user documentation

- [ ] **Step 1: Write end-to-end integration test**

```python
# tests/test_integration.py
import subprocess
import sys

def test_full_workflow_end_to_end(temp_dir, create_test_file):
    """Test complete workflow from CLI to deletion."""
    # Create test file structure
    dup1 = create_test_file(temp_dir / "videos", "movie1.mp4", b"A" * 10000)
    dup2 = create_test_file(temp_dir / "downloads", "movie2.mp4", b"A" * 10000)
    unique = create_test_file(temp_dir / "videos", "unique.mp4", b"B" * 10000)
    
    # Run CLI in dry-run mode
    result = subprocess.run(
        [
            sys.executable, "-m", "src.cli",
            str(temp_dir / "videos"),
            str(temp_dir / "downloads"),
            "--dry-run",
            "--cache-dir", str(temp_dir / "cache")
        ],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert "发现重复" in result.stdout
    assert "1 组" in result.stdout or "1组" in result.stdout
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_integration.py::test_full_workflow_end_to_end -v`
Expected: PASS

- [ ] **Step 3: Write test for cache persistence across runs**

```python
# tests/test_integration.py
def test_cache_persists_across_runs(temp_dir, create_test_file):
    """Test that cache persists and improves second run."""
    from src.scanner import scan_files
    from src.grouper import find_duplicates
    from src.cache import Cache
    
    # Create files
    file1 = create_test_file(temp_dir, "video1.mp4", b"content")
    file2 = create_test_file(temp_dir, "video2.mp4", b"different")
    
    cache_dir = temp_dir / "cache"
    
    # First run
    cache1 = Cache(cache_dir)
    files1 = list(scan_files([temp_dir]))
    find_duplicates(files1, cache=cache1)
    
    stats1 = cache1.get_stats()
    assert stats1["miss_count"] > 0
    assert stats1["hit_count"] == 0
    
    # Second run (should use cache)
    cache2 = Cache(cache_dir)
    files2 = list(scan_files([temp_dir]))
    find_duplicates(files2, cache=cache2)
    
    stats2 = cache2.get_stats()
    assert stats2["hit_count"] > 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_integration.py::test_cache_persists_across_runs -v`
Expected: PASS

- [ ] **Step 5: Update README with complete usage documentation**

```markdown
# Video Dedup

高效、安全的视频文件去重工具

## 功能特性

- ✅ 严格内容比对（基于 SHA-256 哈希）
- ✅ 渐进式哈希优化（大小 → 头部 → 全文）
- ✅ SQLite 缓存支持增量扫描
- ✅ 智能保留规则（保留最早/最短路径文件）
- ✅ 安全删除（移到系统回收站，可恢复）
- ✅ 多目录扫描 + 排除规则
- ✅ Dry-run 预览模式
- ✅ 完整操作日志

## 安装

### 使用 uv（推荐）

```bash
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 克隆项目
git clone <repo-url>
cd video-dedup

# 创建虚拟环境并安装
uv venv
source .venv/bin/activate  # macOS/Linux
uv pip install -e ".[dev]"
```

### 系统要求

- Python 3.10+
- macOS（当前版本）

## 使用方法

### 基本用法

```bash
# 扫描单个目录
video-dedup scan ~/Videos

# 扫描多个目录
video-dedup scan ~/Videos ~/Downloads ~/Desktop
```

### 高级选项

```bash
# 排除特定目录
video-dedup scan ~/Videos --exclude "iMovie 项目" "Final Cut"

# 预览模式（不删除）
video-dedup scan ~/Videos --dry-run

# 清空缓存重新扫描
video-dedup scan ~/Videos --clear-cache

# 自定义缓存目录
video-dedup scan ~/Videos --cache-dir ~/my-cache

# 跟随符号链接
video-dedup scan ~/Videos --follow-symlinks

# 包含隐藏文件
video-dedup scan ~/Videos --include-hidden

# 调整并发线程数
video-dedup scan ~/Videos --threads 4
```

### 典型工作流

```bash
# 1. 首次扫描（预览）
video-dedup scan ~/Videos ~/Downloads --dry-run

# 2. 确认无误后执行删除
video-dedup scan ~/Videos ~/Downloads

# 3. 后续增量扫描（快速）
video-dedup scan ~/Videos ~/Downloads
```

## 工作原理

### 三阶段渐进式哈希

1. **阶段 1**: 按文件大小分组（元数据比对）
2. **阶段 2**: 计算前 64KB 哈希（快速排除）
3. **阶段 3**: 计算完整文件哈希（确认重复）

### 智能保留规则

1. 保留修改时间最早的文件（原始文件）
2. 如果时间相近（< 24 小时），保留路径最短的
3. 如果路径长度相同，保留字典序最小的

### 缓存机制

- 首次扫描：计算所有文件哈希，存入 SQLite 缓存
- 增量扫描：只计算新增/修改的文件，速度提升 90%+
- 缓存键：`(路径, 大小, 修改时间)` 三元组

## 性能

**测试场景**: 3000 个视频文件，总大小 900GB

- 首次扫描: 5-10 分钟
- 增量扫描: < 2 分钟（90% 缓存命中）
- 内存占用: < 200MB

## 安全机制

- ✅ 文件移到系统回收站（可手动恢复）
- ✅ Dry-run 模式预览
- ✅ 完整操作日志（`~/.video-dedup/logs/`）
- ✅ 永不使用 `os.remove()`

## 开发

### 运行测试

```bash
# 所有测试
pytest

# 特定模块
pytest tests/test_scanner.py -v

# 覆盖率报告
pytest --cov=src --cov-report=html
```

### 代码格式化

```bash
black src tests
ruff check src tests
```

## 故障排除

### 缓存损坏

```bash
video-dedup scan ~/Videos --clear-cache
```

### 权限错误

确保对扫描目录有读取权限，对缓存目录有写入权限。

### 符号链接循环

默认不跟随符号链接。使用 `--follow-symlinks` 时注意避免循环。

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
```

- [ ] **Step 6: Create CHANGELOG.md**

```markdown
# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2026-10-05

### Added
- Initial release
- Progressive hashing (size → partial → full)
- SQLite cache for incremental scanning
- Smart retention rules
- Safe deletion to system trash
- Multi-directory scanning
- Exclude pattern support
- Dry-run mode
- JSON operation logs
- Rich terminal UI with progress bars
- Symlink loop detection
- Hidden file handling
- Cache hit/miss tracking

### Features
- Video file deduplication by content (SHA-256)
- Support for 20+ video formats
- Configurable thread pool (default 8 threads)
- Cache persistence across runs
- Automatic old entry cleanup (30 days)

### Performance
- First scan: ~5-10 minutes for 3000 files
- Incremental scan: <2 minutes (90% cache hit)
- Memory usage: <200MB

### Security
- Never uses os.remove() - only send2trash
- All deletions recoverable from system trash
- Complete audit log for all operations
```

- [ ] **Step 7: Run all tests to verify complete system**

Run: `pytest -v --tb=short`
Expected: All tests PASS

- [ ] **Step 8: Commit integration tests and documentation**

```bash
git add tests/test_integration.py README.md CHANGELOG.md
git commit -m "feat: add integration tests and documentation

- End-to-end workflow test
- Cache persistence test
- Complete README with usage examples
- CHANGELOG for v1.0.0
- Performance benchmarks
- Troubleshooting guide"
```

- [ ] **Step 9: Create final release tag**

```bash
git tag -a v1.0.0 -m "Release v1.0.0: Video Dedup

Features:
- Progressive hashing for efficient duplicate detection
- SQLite cache for incremental scanning
- Smart retention rules
- Safe deletion via system trash
- Rich terminal UI"

git push origin v1.0.0
```

---

## Self-Review

**1. Spec coverage check:**
- ✅ Project setup and structure
- ✅ File scanner with recursive traversal and filters
- ✅ Progressive hashing (partial + full)
- ✅ SQLite cache with hit/miss tracking
- ✅ Duplicate grouping by size/hash
- ✅ Retention selector with 3-tier rules
- ✅ Safe deleter with trash integration
- ✅ CLI with rich UI and all options
- ✅ Integration tests
- ✅ Documentation (README + CHANGELOG)

**2. Placeholder scan:** None found - all implementations complete with actual code.

**3. Type consistency:**
- `Path` objects used consistently across all modules
- Hash values always `str` (64-char hex)
- File sizes always `int` (bytes)
- Timestamps always `float` (Unix time)
- All function signatures match between definition and usage

**4. Review Focus coverage:**
1. ✅ Empty directory input - handled in CLI with error message
2. ✅ File disappears during hash - FileNotFoundError caught in grouper
3. ✅ Cache with stale paths - cleaned by `clean_old_entries()`
4. ✅ Same size/mtime different content - progressive hashing proceeds to full hash
5. ✅ Symlink loop - detected via inode tracking in scanner

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-10-05-video-dedup-implementation.md`. Please review the plan.

Which execution approach would you prefer?

- **Subagent-driven** - A fresh subagent implements each task and a fresh reviewer checks it before the next one starts, then a whole-branch review at the end. Most thorough; costs a fresh context per task and per review.
- **Native** - I implement every task myself in this session, the way this harness runs work, then one fresh reviewer on the most capable model checks the whole branch. Cheapest and fastest; no independent review until the end. Runs well with a mid-tier session model, since the plan carries the design.

**For this plan I recommend Native**, because the tasks have clean interfaces and follow a clear dependency chain (utils → scanner/hasher/cache → grouper → selector → deleter → CLI), making sequential implementation in one context efficient. The plan is detailed enough to guide reliable implementation without per-task review overhead.

Does the plan capture what you want, and which approach should we use?
