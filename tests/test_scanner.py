from pathlib import Path
import os

def test_scan_single_directory_with_videos(temp_dir, create_test_file):
    """Test scanning a directory with video files."""
    from src.scanner import scan_files
    from src.file_types import VIDEO_EXTENSIONS

    # Create test files
    create_test_file(temp_dir, "video1.mp4", b"content1")
    create_test_file(temp_dir, "video2.mov", b"content2")
    create_test_file(temp_dir, "document.txt", b"not a video")

    results = list(scan_files([temp_dir], extensions=VIDEO_EXTENSIONS))

    assert len(results) == 2
    assert all(p.suffix.lower() in {'.mp4', '.mov'} for p in results)

def test_scan_nested_directories(temp_dir, create_test_file):
    """Test scanning nested directory structure."""
    from src.scanner import scan_files
    from src.file_types import VIDEO_EXTENSIONS

    create_test_file(temp_dir, "root.mp4", b"root")
    create_test_file(temp_dir, "sub1/video1.mp4", b"sub1")
    create_test_file(temp_dir, "sub1/sub2/video2.avi", b"sub2")

    results = list(scan_files([temp_dir], extensions=VIDEO_EXTENSIONS))

    assert len(results) == 3

def test_scan_with_exclude_patterns(temp_dir, create_test_file):
    """Test excluding directories by pattern."""
    from src.scanner import scan_files
    from src.file_types import VIDEO_EXTENSIONS

    create_test_file(temp_dir, "keep/video1.mp4", b"keep")
    create_test_file(temp_dir, "iMovie 项目/video2.mp4", b"exclude")
    create_test_file(temp_dir, "Final Cut/video3.mov", b"exclude")

    results = list(scan_files([temp_dir], extensions=VIDEO_EXTENSIONS, exclude_patterns=["iMovie 项目", "Final Cut"]))

    assert len(results) == 1
    assert "keep" in str(results[0])

def test_scan_skips_hidden_files_by_default(temp_dir, create_test_file):
    """Test that hidden files are skipped by default."""
    from src.scanner import scan_files
    from src.file_types import VIDEO_EXTENSIONS

    create_test_file(temp_dir, "visible.mp4", b"visible")
    create_test_file(temp_dir, ".hidden.mp4", b"hidden")

    results = list(scan_files([temp_dir], extensions=VIDEO_EXTENSIONS))

    assert len(results) == 1
    assert results[0].name == "visible.mp4"

def test_scan_includes_hidden_files_when_enabled(temp_dir, create_test_file):
    """Test that hidden files are included when flag is set."""
    from src.scanner import scan_files
    from src.file_types import VIDEO_EXTENSIONS

    create_test_file(temp_dir, "visible.mp4", b"visible")
    create_test_file(temp_dir, ".hidden.mp4", b"hidden")

    results = list(scan_files([temp_dir], extensions=VIDEO_EXTENSIONS, include_hidden=True))

    assert len(results) == 2

def test_scan_multiple_root_directories(temp_dir, create_test_file):
    """Test scanning multiple independent directories."""
    from src.scanner import scan_files
    from src.file_types import VIDEO_EXTENSIONS

    dir1 = temp_dir / "dir1"
    dir2 = temp_dir / "dir2"

    create_test_file(dir1, "video1.mp4", b"dir1")
    create_test_file(dir2, "video2.mov", b"dir2")

    results = list(scan_files([dir1, dir2], extensions=VIDEO_EXTENSIONS))

    assert len(results) == 2

def test_scan_empty_directory_list():
    """Test scanning with empty directory list."""
    from src.scanner import scan_files
    from src.file_types import VIDEO_EXTENSIONS

    results = list(scan_files([], extensions=VIDEO_EXTENSIONS))

    assert results == []

def test_scan_detects_symlink_loop(temp_dir, create_test_file):
    """Test that symlink loops are detected and don't cause infinite recursion."""
    from src.scanner import scan_files
    from src.file_types import VIDEO_EXTENSIONS

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
    results = list(scan_files([temp_dir], extensions=VIDEO_EXTENSIONS, follow_symlinks=True))

    assert len(results) == 1  # Should find video once, not infinite times

def test_scan_skips_symlink_files_and_directories_by_default(temp_dir, create_test_file):
    """Symlink entries are not traversed unless explicitly enabled."""
    from src.scanner import scan_files
    from src.file_types import VIDEO_EXTENSIONS

    target_dir = temp_dir / "target"
    target_file = create_test_file(target_dir, "video.mp4", b"content")
    (temp_dir / "linked-dir").symlink_to(target_dir)
    (temp_dir / "linked-file.mp4").symlink_to(target_file)

    results = list(scan_files([temp_dir], extensions=VIDEO_EXTENSIONS))
    assert len(results) == 1
    assert results[0] == target_file.resolve()

def test_scan_follows_symlinks_without_revisiting_directories(temp_dir, create_test_file):
    """Following a directory alias does not duplicate files or recurse forever."""
    from src.scanner import scan_files
    from src.file_types import VIDEO_EXTENSIONS

    target_dir = temp_dir / "target"
    target_file = create_test_file(target_dir, "video.mp4", b"content")
    (temp_dir / "linked-dir").symlink_to(target_dir)

    results = list(scan_files([temp_dir], extensions=VIDEO_EXTENSIONS, follow_symlinks=True))

    assert results.count(target_file.resolve()) == 1

def test_scan_follows_file_symlinks_without_duplicate_paths(temp_dir, create_test_file):
    """A symlink alias to a video is returned once as its resolved target."""
    from src.scanner import scan_files
    from src.file_types import VIDEO_EXTENSIONS

    target_dir = temp_dir / "target"
    target_file = create_test_file(target_dir, "video.mp4", b"content")
    (temp_dir / "linked-file.mp4").symlink_to(target_file)

    results = list(scan_files([temp_dir], extensions=VIDEO_EXTENSIONS, follow_symlinks=True))

    assert len(results) == 1
    assert results[0] == target_file.resolve()

def test_scan_image_files(temp_dir, create_test_file):
    """测试扫描图片文件"""
    from src.scanner import scan_files
    from src.file_types import IMAGE_EXTENSIONS

    create_test_file(temp_dir, "photo1.jpg", b"photo1")
    create_test_file(temp_dir, "photo2.PNG", b"photo2")  # 大写扩展名
    create_test_file(temp_dir, "image.heic", b"heic")
    create_test_file(temp_dir, "video.mp4", b"video")  # 应被过滤

    results = list(scan_files([temp_dir], extensions=IMAGE_EXTENSIONS))

    assert len(results) == 3
    assert all(p.suffix.lower() in IMAGE_EXTENSIONS for p in results)

def test_scan_filters_by_extensions_in_mixed_directory(temp_dir, create_test_file):
    """Review Focus: 混合目录中只返回指定类型的文件"""
    from src.scanner import scan_files
    from src.file_types import IMAGE_EXTENSIONS

    create_test_file(temp_dir, "photo.jpg", b"photo")
    create_test_file(temp_dir, "video.mp4", b"video")
    create_test_file(temp_dir, "document.pdf", b"doc")
    create_test_file(temp_dir, "image.png", b"image")

    results = list(scan_files([temp_dir], extensions=IMAGE_EXTENSIONS))

    assert len(results) == 2
    assert all(p.suffix.lower() in {'.jpg', '.png'} for p in results)

def test_scan_case_insensitive_extensions(temp_dir, create_test_file):
    """Review Focus: 扩展名大小写不敏感"""
    from src.scanner import scan_files
    from src.file_types import IMAGE_EXTENSIONS

    # 不同大小写放在不同子目录，避免大小写不敏感文件系统上互相覆盖
    create_test_file(temp_dir, "a/Photo.JPG", b"content-a")
    create_test_file(temp_dir, "b/photo.jpg", b"content-b")
    create_test_file(temp_dir, "c/PHOTO.Jpg", b"content-c")

    results = list(scan_files([temp_dir], extensions=IMAGE_EXTENSIONS))

    assert len(results) == 3
