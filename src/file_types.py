"""文件类型定义和配置

[INPUT]: 无外部依赖（仅标准库 enum / dataclasses）
[OUTPUT]: FileType, FileTypeConfig, VIDEO_EXTENSIONS, IMAGE_EXTENSIONS, get_config
[POS]: 文件类型配置中心，供 scanner / selector / cli 等模块查询扩展名与默认保留策略
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
from enum import Enum
from dataclasses import dataclass


class FileType(Enum):
    """支持的文件类型"""
    VIDEO = "video"
    IMAGE = "image"


@dataclass
class FileTypeConfig:
    """文件类型配置"""
    extensions: set[str]
    default_strategy: str
    display_name: str


VIDEO_EXTENSIONS = {
    '.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.m4v',
    '.mpg', '.mpeg', '.3gp', '.webm', '.ogv', '.ts', '.mts',
    '.vob', '.rm', '.rmvb', '.asf', '.m2ts', '.divx'
}


IMAGE_EXTENSIONS = {
    # 常见格式
    '.jpg', '.jpeg',
    '.png',
    '.gif',
    '.bmp',
    '.webp',
    # RAW格式
    '.raw', '.cr2', '.nef', '.arw',
    # 其他格式
    '.tiff', '.tif',
    '.heic', '.heif',
    '.svg'
}


FILE_TYPE_CONFIGS = {
    FileType.VIDEO: FileTypeConfig(
        extensions=VIDEO_EXTENSIONS,
        default_strategy="oldest",
        display_name="视频"
    ),
    FileType.IMAGE: FileTypeConfig(
        extensions=IMAGE_EXTENSIONS,
        default_strategy="newest",
        display_name="图片"
    )
}


def get_config(file_type: FileType) -> FileTypeConfig:
    """获取文件类型配置"""
    return FILE_TYPE_CONFIGS[file_type]
