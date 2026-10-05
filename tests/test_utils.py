# tests/test_utils.py
def test_video_extensions_contains_common_formats():
    from src.utils import VIDEO_EXTENSIONS
    assert '.mp4' in VIDEO_EXTENSIONS
    assert '.mov' in VIDEO_EXTENSIONS
    assert '.avi' in VIDEO_EXTENSIONS
    assert '.mkv' in VIDEO_EXTENSIONS
    assert len(VIDEO_EXTENSIONS) >= 15  # At least 15 formats

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

def test_format_duration_seconds():
    from src.utils import format_duration
    assert format_duration(45) == "45 秒"

def test_format_duration_minutes():
    from src.utils import format_duration
    assert format_duration(125) == "2 分 5 秒"

def test_format_duration_hours():
    from src.utils import format_duration
    assert format_duration(3725) == "1 小时 2 分 5 秒"
