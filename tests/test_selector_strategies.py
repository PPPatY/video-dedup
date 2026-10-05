"""Tests for selector retention strategies."""
import os
import time

DAY = 86400


def _set_mtime(path, mtime):
    os.utime(path, (mtime, mtime))


def test_select_newest_strategy(temp_dir, create_test_file):
    """测试 newest 策略保留最新文件"""
    from src.selector import select_files_to_keep

    file1 = create_test_file(temp_dir, "old.jpg", b"content")
    file2 = create_test_file(temp_dir, "mid.jpg", b"content")
    file3 = create_test_file(temp_dir, "new.jpg", b"content")

    # mtime 间隔超过 24h，避免触发"时间相近"规则
    now = time.time()
    _set_mtime(file1, now - 10 * DAY)
    _set_mtime(file2, now - 5 * DAY)
    _set_mtime(file3, now)

    selections = select_files_to_keep([[file1, file2, file3]], strategy="newest")

    assert file3 in selections
    assert set(selections[file3]) == {file1, file2}


def test_select_oldest_strategy_default(temp_dir, create_test_file):
    """测试 oldest 策略（默认，向后兼容）"""
    from src.selector import select_files_to_keep

    file1 = create_test_file(temp_dir, "old.mp4", b"content")
    file2 = create_test_file(temp_dir, "new.mp4", b"content")

    now = time.time()
    _set_mtime(file1, now - 5 * DAY)
    _set_mtime(file2, now)

    # 不指定 strategy，应该默认 oldest
    selections = select_files_to_keep([[file1, file2]])

    assert file1 in selections
    assert selections[file1] == [file2]


def test_select_oldest_strategy_explicit(temp_dir, create_test_file):
    """测试明确指定 oldest 策略"""
    from src.selector import select_files_to_keep

    file1 = create_test_file(temp_dir, "old.jpg", b"content")
    file2 = create_test_file(temp_dir, "mid.jpg", b"content")
    file3 = create_test_file(temp_dir, "new.jpg", b"content")

    now = time.time()
    _set_mtime(file1, now - 10 * DAY)
    _set_mtime(file2, now - 5 * DAY)
    _set_mtime(file3, now)

    selections = select_files_to_keep([[file1, file2, file3]], strategy="oldest")

    assert file1 in selections
    assert set(selections[file1]) == {file2, file3}


def test_strategy_with_similar_time_shortest_path(temp_dir, create_test_file):
    """测试时间相近时保留路径最短的"""
    from src.selector import select_files_to_keep

    file1 = create_test_file(temp_dir, "a/very/long/path/file.jpg", b"content")
    file2 = create_test_file(temp_dir, "short/file.jpg", b"content")

    mtime = time.time()
    _set_mtime(file1, mtime)
    _set_mtime(file2, mtime)

    selections = select_files_to_keep([[file1, file2]], strategy="newest")

    # 应该保留路径更短的 file2
    assert file2 in selections
    assert selections[file2] == [file1]


def test_similar_time_threshold_24_hours(temp_dir, create_test_file):
    """Review Focus: 时间相近阈值为 24 小时"""
    from src.selector import select_files_to_keep, TIME_SIMILARITY_THRESHOLD

    assert TIME_SIMILARITY_THRESHOLD == 86400

    long_file = create_test_file(temp_dir, "a/very/long/path/file.jpg", b"content")
    short_file = create_test_file(temp_dir, "s/file.jpg", b"content")

    base = time.time()

    # 相差 23 小时（阈值内）：无论哪种策略，都保留路径更短的文件
    _set_mtime(long_file, base - 23 * 3600)
    _set_mtime(short_file, base)
    for strategy in ("oldest", "newest"):
        selections = select_files_to_keep([[long_file, short_file]], strategy=strategy)
        assert list(selections) == [short_file]

    # 相差 25 小时（阈值外）：按策略保留
    _set_mtime(long_file, base - 25 * 3600)
    assert list(select_files_to_keep([[long_file, short_file]], strategy="oldest")) == [long_file]
    assert list(select_files_to_keep([[long_file, short_file]], strategy="newest")) == [short_file]


def test_manual_strategy_overrides_default(temp_dir, create_test_file):
    """Review Focus: 手动策略应覆盖默认策略"""
    from src.selector import select_files_to_keep

    file1 = create_test_file(temp_dir, "old.jpg", b"content")
    file2 = create_test_file(temp_dir, "new.jpg", b"content")

    now = time.time()
    _set_mtime(file1, now - 5 * DAY)
    _set_mtime(file2, now)

    # 图片默认是 newest，但手动指定 oldest
    selections = select_files_to_keep([[file1, file2]], strategy="oldest")

    # 应该保留 old（不是 new）
    assert file1 in selections
    assert selections[file1] == [file2]
