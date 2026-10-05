"""Tests for src.file_types."""


def test_file_type_enum_has_video_and_image():
    """测试 FileType 枚举包含 VIDEO 和 IMAGE"""
    from src.file_types import FileType

    assert FileType.VIDEO.value == "video"
    assert FileType.IMAGE.value == "image"
    assert len(FileType) == 2


def test_video_extensions_contains_common_formats():
    """测试视频扩展名包含常见格式"""
    from src.file_types import VIDEO_EXTENSIONS

    assert '.mp4' in VIDEO_EXTENSIONS
    assert '.mov' in VIDEO_EXTENSIONS
    assert '.avi' in VIDEO_EXTENSIONS
    assert '.mkv' in VIDEO_EXTENSIONS
    assert len(VIDEO_EXTENSIONS) >= 20

    # 所有扩展名应该是小写
    assert all(ext.islower() for ext in VIDEO_EXTENSIONS)
    assert all(ext.startswith('.') for ext in VIDEO_EXTENSIONS)


def test_image_extensions_contains_common_formats():
    """测试图片扩展名包含常见格式"""
    from src.file_types import IMAGE_EXTENSIONS

    assert '.jpg' in IMAGE_EXTENSIONS
    assert '.jpeg' in IMAGE_EXTENSIONS
    assert '.png' in IMAGE_EXTENSIONS
    assert '.gif' in IMAGE_EXTENSIONS
    assert '.heic' in IMAGE_EXTENSIONS
    assert len(IMAGE_EXTENSIONS) >= 15

    # 所有扩展名应该是小写
    assert all(ext.islower() for ext in IMAGE_EXTENSIONS)
    assert all(ext.startswith('.') for ext in IMAGE_EXTENSIONS)


def test_file_type_config_structure():
    """测试 FileTypeConfig 数据结构"""
    from src.file_types import FileTypeConfig

    config = FileTypeConfig(
        extensions={'.mp4'},
        default_strategy="oldest",
        display_name="测试"
    )

    assert config.extensions == {'.mp4'}
    assert config.default_strategy == "oldest"
    assert config.display_name == "测试"


def test_get_config_for_video():
    """测试获取视频配置"""
    from src.file_types import FileType, get_config

    config = get_config(FileType.VIDEO)

    assert '.mp4' in config.extensions
    assert config.default_strategy == "oldest"
    assert config.display_name == "视频"


def test_get_config_for_image():
    """测试获取图片配置"""
    from src.file_types import FileType, get_config

    config = get_config(FileType.IMAGE)

    assert '.jpg' in config.extensions
    assert '.png' in config.extensions
    assert config.default_strategy == "newest"
    assert config.display_name == "图片"


def test_extensions_are_lowercase():
    """Review Focus: 所有扩展名必须小写以支持大小写不敏感匹配"""
    from src.file_types import VIDEO_EXTENSIONS, IMAGE_EXTENSIONS

    all_extensions = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS

    for ext in all_extensions:
        assert ext == ext.lower(), f"扩展名 {ext} 不是小写"
        assert ext.startswith('.'), f"扩展名 {ext} 必须以点开头"
