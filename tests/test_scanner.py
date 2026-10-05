from pathlib import Path
import os

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

def test_scan_nested_directories(temp_dir, create_test_file):
    """Test scanning nested directory structure."""
    from src.scanner import scan_files

    create_test_file(temp_dir, "root.mp4", b"root")
    create_test_file(temp_dir, "sub1/video1.mp4", b"sub1")
    create_test_file(temp_dir, "sub1/sub2/video2.avi", b"sub2")

    results = list(scan_files([temp_dir]))

    assert len(results) == 3

def test_scan_with_exclude_patterns(temp_dir, create_test_file):
    """Test excluding directories by pattern."""
    from src.scanner import scan_files

    create_test_file(temp_dir, "keep/video1.mp4", b"keep")
    create_test_file(temp_dir, "iMovie 项目/video2.mp4", b"exclude")
    create_test_file(temp_dir, "Final Cut/video3.mov", b"exclude")

    results = list(scan_files([temp_dir], exclude_patterns=["iMovie 项目", "Final Cut"]))

    assert len(results) == 1
    assert "keep" in str(results[0])

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

def test_scan_multiple_root_directories(temp_dir, create_test_file):
    """Test scanning multiple independent directories."""
    from src.scanner import scan_files

    dir1 = temp_dir / "dir1"
    dir2 = temp_dir / "dir2"

    create_test_file(dir1, "video1.mp4", b"dir1")
    create_test_file(dir2, "video2.mov", b"dir2")

    results = list(scan_files([dir1, dir2]))

    assert len(results) == 2

def test_scan_empty_directory_list():
    """Test scanning with empty directory list."""
    from src.scanner import scan_files

    results = list(scan_files([]))

    assert results == []

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
