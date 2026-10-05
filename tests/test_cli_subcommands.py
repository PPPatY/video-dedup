"""CLI 子命令架构测试

[INPUT]: depends on src.cli (通过 subprocess 调用 python -m src.cli)
[OUTPUT]: 子命令帮助 / 旧用法检测 / 执行 / 保留策略 的测试用例
[POS]: tests 模块中 CLI 层的端到端测试
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
import subprocess
import sys


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "src.cli", *map(str, args)],
        capture_output=True,
        text=True,
    )


def test_video_subcommand_help():
    """测试 video 子命令帮助信息"""
    result = run_cli("video", "--help")

    assert result.returncode == 0
    assert "视频文件去重" in result.stdout
    assert "--keep-strategy" in result.stdout


def test_image_subcommand_help():
    """测试 image 子命令帮助信息"""
    result = run_cli("image", "--help")

    assert result.returncode == 0
    assert "图片文件去重" in result.stdout
    assert "--keep-strategy" in result.stdout


def test_main_help_shows_subcommands():
    """测试主帮助显示子命令"""
    result = run_cli("--help")

    assert result.returncode == 0
    assert "video" in result.stdout
    assert "image" in result.stdout


def test_old_usage_shows_friendly_error(temp_dir):
    """Review Focus: 旧用法应显示友好错误提示"""
    test_dir = temp_dir / "test"
    test_dir.mkdir()

    result = run_cli(test_dir)
    output = result.stdout + result.stderr

    assert result.returncode == 1
    assert "错误" in output
    assert "v2.0" in output
    assert "新用法" in output
    assert "video-dedup video" in output


def test_video_subcommand_execution(temp_dir, create_test_file, tmp_path):
    """测试 video 子命令执行"""
    create_test_file(temp_dir, "a.mp4", b"content")
    create_test_file(temp_dir, "b.mp4", b"content")

    result = run_cli("video", temp_dir, "--dry-run", "--cache-dir", tmp_path / "cache")

    assert result.returncode == 0
    assert "视频" in result.stdout
    assert "重复" in result.stdout or "发现" in result.stdout


def test_image_subcommand_execution(temp_dir, create_test_file, tmp_path):
    """测试 image 子命令执行"""
    create_test_file(temp_dir, "a.jpg", b"content")
    create_test_file(temp_dir, "b.jpg", b"content")

    result = run_cli("image", temp_dir, "--dry-run", "--cache-dir", tmp_path / "cache")

    assert result.returncode == 0
    assert "图片" in result.stdout
    assert "重复" in result.stdout or "发现" in result.stdout


def test_image_subcommand_ignores_video_files(temp_dir, create_test_file, tmp_path):
    """image 子命令不应扫描视频文件"""
    create_test_file(temp_dir, "a.mp4", b"content")
    create_test_file(temp_dir, "b.mp4", b"content")

    result = run_cli("image", temp_dir, "--dry-run", "--cache-dir", tmp_path / "cache")

    assert result.returncode == 0
    assert "未找到图片文件" in result.stdout


def test_keep_strategy_parameter(temp_dir, create_test_file, tmp_path):
    """测试 --keep-strategy 参数"""
    create_test_file(temp_dir, "a.jpg", b"content")
    create_test_file(temp_dir, "b.jpg", b"content")

    result = run_cli(
        "image", temp_dir, "--keep-strategy", "oldest", "--dry-run",
        "--cache-dir", tmp_path / "cache",
    )

    assert result.returncode == 0
    assert "保留最早修改的文件" in result.stdout


def test_smart_strategy_resolves_per_file_type(temp_dir, create_test_file, tmp_path):
    """smart 策略：视频默认 oldest，图片默认 newest"""
    create_test_file(temp_dir, "a.jpg", b"content")
    create_test_file(temp_dir, "b.jpg", b"content")
    create_test_file(temp_dir, "a.mp4", b"content")
    create_test_file(temp_dir, "b.mp4", b"content")
    cache = tmp_path / "cache"

    image = run_cli("image", temp_dir, "--dry-run", "--cache-dir", cache)
    video = run_cli("video", temp_dir, "--dry-run", "--cache-dir", cache)

    assert "保留最新修改的文件" in image.stdout
    assert "保留最早修改的文件" in video.stdout
