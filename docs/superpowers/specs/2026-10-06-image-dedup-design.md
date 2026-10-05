# 图片去重功能设计规格

**日期**: 2026-10-06  
**版本**: 2.0.0  
**作者**: Claude Opus 5.5

## 1. 概述

### 1.1 目标

将 video-dedup 从单一用途的视频去重工具扩展为通用媒体文件去重工具，支持图片和视频两种文件类型。

### 1.2 动机

用户需要统一的去重解决方案来管理不同类型的媒体文件，而不是为每种类型维护不同的工具。通过抽象化现有架构，可以以最小成本支持图片去重，并为未来支持更多文件类型（如音频）奠定基础。

### 1.3 非目标

- **不支持**感知哈希（perceptual hashing）- 仅支持精确内容匹配
- **不处理** EXIF 数据或元数据（仅基于文件内容）
- **不支持**视频和图片的混合去重（在单次扫描中同时处理两种类型）
- **不添加**新的外部依赖（保持 stdlib + rich + send2trash）

---

## 2. 用户体验

### 2.1 命令行接口

**新的子命令结构**：

```bash
# 视频去重（保留最早的文件）
video-dedup video ~/Videos

# 图片去重（保留最新的文件）
video-dedup image ~/Photos

# 手动覆盖保留策略
video-dedup video ~/Videos --keep-strategy newest
video-dedup image ~/Photos --keep-strategy oldest

# 智能策略（默认，根据文件类型自动选择）
video-dedup video ~/Videos --keep-strategy smart
video-dedup image ~/Photos --keep-strategy smart

# 其他选项照常工作
video-dedup image ~/Photos --dry-run --exclude "Thumbnails"
```

### 2.2 保留策略

**智能策略行为**：

| 文件类型 | 默认策略 | 理由 |
|---------|---------|------|
| 视频 | `oldest` | 原始录制最重要 |
| 图片 | `newest` | 编辑/导出版本通常更好 |

**策略详细说明**：

- **oldest**（保留最早）
  1. 按修改时间升序排序
  2. 保留最早的文件
  3. 时间相近（<24h）时，保留路径最短的
  4. 路径长度相同时，保留字典序最小的

- **newest**（保留最新）
  1. 按修改时间降序排序
  2. 保留最新的文件
  3. 时间相近（<24h）时，保留路径最短的
  4. 路径长度相同时，保留字典序最小的

- **smart**（智能）
  - 在 CLI 层解析为对应文件类型的默认策略
  - `video` → `oldest`
  - `image` → `newest`

### 2.3 输出示例

```
🔍 扫描图片文件...

扫描目录:
  • /Users/pat/Photos

找到 350 个图片文件
查找重复文件...

==================================================
✓ 扫描完成 (用时 12 秒)

📊 统计:
  • 总文件数: 350 个图片
  • 发现重复: 5 组（15 个文件可删除）
  • 可释放空间: 42.3 MB
  • 缓存命中率: 85.2%

🗑️  删除策略:
  • 保留最新修改的文件
  • 时间相近时保留路径最短的

确认删除 15 个重复文件？[y/N]
```

---

## 3. 架构设计

### 3.1 设计原则

**最小抽象层（Minimal Abstraction Layer）**：

- 引入 `FileType` 枚举和配置字典
- 最小化对现有模块的改动
- 保持代码简单直接，避免过度设计
- 遵循 YAGNI 原则（You Aren't Gonna Need It）

### 3.2 新增模块

**`src/file_types.py`**（新增文件，~60行）

```python
"""文件类型定义和配置"""
from enum import Enum
from dataclasses import dataclass

class FileType(Enum):
    """支持的文件类型"""
    VIDEO = "video"
    IMAGE = "image"

@dataclass
class FileTypeConfig:
    """文件类型配置"""
    extensions: set[str]         # 文件扩展名集合
    default_strategy: str        # 默认保留策略 "oldest" | "newest"
    display_name: str            # 显示名称（用于UI）

# 视频配置
VIDEO_EXTENSIONS = {
    '.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.m4v',
    '.mpg', '.mpeg', '.3gp', '.webm', '.ogv', '.ts', '.mts',
    '.vob', '.rm', '.rmvb', '.asf', '.m2ts', '.divx'
}

# 图片配置
IMAGE_EXTENSIONS = {
    # 常见格式
    '.jpg', '.jpeg',    # JPEG
    '.png',             # PNG
    '.gif',             # GIF
    '.bmp',             # Bitmap
    '.webp',            # WebP
    
    # RAW格式
    '.raw', '.cr2', '.nef', '.arw',  # Canon/Nikon/Sony RAW
    
    # 其他格式
    '.tiff', '.tif',    # TIFF
    '.heic', '.heif',   # HEIC (iPhone)
    '.svg'              # SVG
}

# 文件类型配置映射
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
```

### 3.3 现有模块改动

#### 3.3.1 `src/utils.py`（删除）

**改动**：
- 删除 `VIDEO_EXTENSIONS` 常量（迁移到 `file_types.py`）
- `format_size()` 和 `format_duration()` 保持不变

**改动量**: ~5行删除

---

#### 3.3.2 `src/scanner.py`（参数化）

**改动前**：
```python
def scan_files(
    root_dirs: list[Path],
    exclude_patterns: list[str] | None = None,
    follow_symlinks: bool = False,
    include_hidden: bool = False
) -> Iterator[Path]:
    from src.utils import VIDEO_EXTENSIONS
    ...
    if entry.suffix.lower() in VIDEO_EXTENSIONS:
        yield entry.resolve()
```

**改动后**：
```python
def scan_files(
    root_dirs: list[Path],
    extensions: set[str],  # 新增参数
    exclude_patterns: list[str] | None = None,
    follow_symlinks: bool = False,
    include_hidden: bool = False
) -> Iterator[Path]:
    ...
    if entry.suffix.lower() in extensions:  # 使用参数
        yield entry.resolve()
```

**改动量**: ~5行修改

---

#### 3.3.3 `src/selector.py`（策略参数）

**改动前**：
```python
def select_files_to_keep(
    duplicate_groups: list[list[Path]]
) -> dict[Path, list[Path]]:
    # 硬编码保留 oldest
    sorted_files = sorted(group, key=lambda f: os.path.getmtime(f))
    ...
```

**改动后**：
```python
def select_files_to_keep(
    duplicate_groups: list[list[Path]],
    strategy: str = "oldest"  # 新增参数: "oldest" | "newest"
) -> dict[Path, list[Path]]:
    """
    根据策略选择要保留的文件
    
    Args:
        duplicate_groups: 重复文件分组
        strategy: 保留策略
            - "oldest": 保留最早修改的文件
            - "newest": 保留最新修改的文件
    
    Returns:
        字典映射 {要保留的文件: [要删除的文件列表]}
    """
    result = {}
    
    for group in duplicate_groups:
        if len(group) < 2:
            continue
        
        # 根据策略排序
        if strategy == "newest":
            sorted_files = sorted(group, key=lambda f: os.path.getmtime(f), reverse=True)
        else:  # oldest
            sorted_files = sorted(group, key=lambda f: os.path.getmtime(f))
        
        oldest_file = sorted_files[0]
        oldest_mtime = os.path.getmtime(oldest_file)
        
        # 时间相近的文件（<24小时）
        similar_time_files = [
            f for f in sorted_files
            if abs(os.path.getmtime(f) - oldest_mtime) < TIME_SIMILARITY_THRESHOLD
        ]
        
        if len(similar_time_files) > 1:
            # 路径最短 → 字典序
            to_keep = min(similar_time_files, key=lambda f: (len(str(f)), str(f)))
        else:
            to_keep = oldest_file
        
        to_delete = [f for f in group if f != to_keep]
        result[to_keep] = to_delete
    
    return result
```

**改动量**: ~20行修改

---

#### 3.3.4 `src/cli.py`（子命令重构）

**改动前**：单一入口 `video-dedup <dirs>`

**改动后**：子命令架构

```python
import argparse
import sys
from pathlib import Path
from rich.console import Console
from src.file_types import FileType, get_config
from src.scanner import scan_files
from src.grouper import find_duplicates
from src.selector import select_files_to_keep
from src.deleter import delete_files, create_deletion_log
from src.cache import Cache
from src.utils import format_size, format_duration
import time

console = Console()

def create_parser() -> argparse.ArgumentParser:
    """创建参数解析器"""
    parser = argparse.ArgumentParser(
        prog="video-dedup",
        description="通用媒体文件去重工具"
    )
    
    # 子命令
    subparsers = parser.add_subparsers(dest="command", required=True, help="子命令")
    
    # 共享参数定义函数
    def add_common_args(subparser):
        subparser.add_argument(
            "directories",
            nargs="+",
            type=Path,
            help="要扫描的目录"
        )
        subparser.add_argument(
            "--exclude",
            nargs="+",
            default=[],
            help="排除的目录名称"
        )
        subparser.add_argument(
            "--dry-run",
            action="store_true",
            help="预览模式，不实际删除"
        )
        subparser.add_argument(
            "--cache-dir",
            type=Path,
            default=Path.home() / ".video-dedup",
            help="缓存目录"
        )
        subparser.add_argument(
            "--clear-cache",
            action="store_true",
            help="清空缓存"
        )
        subparser.add_argument(
            "--keep-strategy",
            choices=["oldest", "newest", "smart"],
            default="smart",
            help="保留策略（默认: smart - 根据文件类型自动选择）"
        )
        subparser.add_argument(
            "--follow-symlinks",
            action="store_true",
            help="跟随符号链接"
        )
        subparser.add_argument(
            "--include-hidden",
            action="store_true",
            help="包含隐藏文件"
        )
    
    # video 子命令
    video_parser = subparsers.add_parser(
        "video",
        help="视频文件去重"
    )
    add_common_args(video_parser)
    
    # image 子命令
    image_parser = subparsers.add_parser(
        "image",
        help="图片文件去重"
    )
    add_common_args(image_parser)
    
    return parser

def process_dedup(args, file_type: FileType):
    """通用去重处理流程"""
    config = get_config(file_type)
    
    # 处理 smart 策略
    if args.keep_strategy == "smart":
        strategy = config.default_strategy
    else:
        strategy = args.keep_strategy
    
    console.print(f"[green]🔍 扫描{config.display_name}文件...[/green]\n")
    
    # 初始化缓存
    cache = None
    if args.cache_dir:
        cache = Cache(args.cache_dir)
        if args.clear_cache:
            console.print("清空缓存...")
            cache.clear()
    
    # 显示扫描目录
    console.print("扫描目录:")
    for directory in args.directories:
        console.print(f"  • {directory}")
    
    if args.exclude:
        console.print("排除规则:")
        for pattern in args.exclude:
            console.print(f"  • {pattern}")
    
    start_time = time.time()
    
    # 扫描文件
    files = list(scan_files(
        args.directories,
        extensions=config.extensions,
        exclude_patterns=args.exclude,
        follow_symlinks=args.follow_symlinks,
        include_hidden=args.include_hidden
    ))
    
    if not files:
        console.print(f"\n[yellow]未找到{config.display_name}文件[/yellow]")
        sys.exit(0)
    
    console.print(f"\n找到 {len(files)} 个{config.display_name}文件")
    
    # 查找重复
    console.print("查找重复文件...")
    duplicate_groups = find_duplicates(files, cache=cache)
    
    if not duplicate_groups:
        console.print(f"\n[green]✓ 未发现重复{config.display_name}[/green]")
        sys.exit(0)
    
    # 选择保留/删除
    selections = select_files_to_keep(duplicate_groups, strategy=strategy)
    
    total_duplicates = sum(len(to_delete) for to_delete in selections.values())
    total_size = sum(
        sum(f.stat().st_size for f in to_delete)
        for to_delete in selections.values()
    )
    
    # 显示统计
    console.print("\n" + "=" * 50)
    console.print(f"[green]✓ 扫描完成[/green] (用时 {format_duration(time.time() - start_time)})")
    console.print(f"\n📊 统计:")
    console.print(f"  • 总文件数: {len(files)} 个{config.display_name}")
    console.print(f"  • 发现重复: {len(duplicate_groups)} 组（{total_duplicates} 个文件可删除）")
    console.print(f"  • 可释放空间: {format_size(total_size)}")
    
    if cache:
        stats = cache.get_stats()
        if stats["hit_count"] + stats["miss_count"] > 0:
            hit_rate = stats["hit_count"] / (stats["hit_count"] + stats["miss_count"])
            console.print(f"  • 缓存命中率: {hit_rate:.1%}")
    
    # 显示策略
    strategy_desc = {
        "oldest": "保留最早修改的文件",
        "newest": "保留最新修改的文件"
    }
    console.print(f"\n🗑️  删除策略:")
    console.print(f"  • {strategy_desc[strategy]}")
    console.print(f"  • 时间相近时保留路径最短的")
    
    # 确认删除
    if args.dry_run:
        console.print(f"\n[yellow]⚠️  预览模式（--dry-run）：不会实际删除文件[/yellow]")
        all_to_delete = [f for to_delete in selections.values() for f in to_delete]
        result = delete_files(all_to_delete, dry_run=True)
        log_path = create_deletion_log(
            args.cache_dir / "logs",
            result,
            duplicate_groups
        )
        console.print(f"删除计划已保存到: {log_path}")
    else:
        console.print(f"\n确认删除 {total_duplicates} 个重复文件？[y/N] ", end="")
        response = input().strip().lower()
        
        if response == 'y':
            all_to_delete = [f for to_delete in selections.values() for f in to_delete]
            result = delete_files(all_to_delete)
            
            console.print(f"\n[green]✓ 操作完成[/green]")
            console.print(f"  • 已删除: {len(result['success'])} 个文件")
            console.print(f"  • 已释放: {format_size(total_size)}")
            console.print(f"  • 文件已移至回收站（可恢复）")
            
            log_path = create_deletion_log(args.cache_dir / "logs", result, duplicate_groups)
            console.print(f"  • 操作日志: {log_path}")
            
            if result["failed"]:
                console.print(f"\n[yellow]警告: {len(result['failed'])} 个文件删除失败（详见日志）[/yellow]")
        else:
            console.print("\n取消操作")
    
    sys.exit(0)

def main():
    """主入口"""
    # 检测旧用法并提示
    if len(sys.argv) >= 2 and sys.argv[1] not in ['video', 'image', '-h', '--help', '--version']:
        potential_path = Path(sys.argv[1])
        if potential_path.exists():
            console.print("[red]错误：video-dedup v2.0 需要指定子命令[/red]")
            console.print("\n旧用法: video-dedup <目录>")
            console.print("新用法: video-dedup video <目录>")
            console.print("       video-dedup image <目录>")
            console.print("\n运行 'video-dedup --help' 查看详情")
            sys.exit(1)
    
    parser = create_parser()
    args = parser.parse_args()
    
    # 根据子命令确定文件类型
    file_type = FileType.VIDEO if args.command == "video" else FileType.IMAGE
    
    # 执行去重
    process_dedup(args, file_type)

if __name__ == "__main__":
    main()
```

**改动量**: ~200行重构（提取共享逻辑 + 子命令结构）

---

#### 3.3.5 不需要改动的模块

以下模块已经是类型无关的，**无需任何修改**：

- ✅ `src/hasher.py` - SHA-256 对任何文件都一样
- ✅ `src/cache.py` - 缓存机制与文件类型无关
- ✅ `src/grouper.py` - 三阶段哈希逻辑通用
- ✅ `src/deleter.py` - 删除逻辑与文件类型无关

---

## 4. 数据流

### 4.1 完整处理流程

```
用户输入
  ↓
video-dedup image ~/Photos --keep-strategy smart --dry-run
  ↓
CLI 解析
  ├─ command = "image"
  ├─ file_type = FileType.IMAGE
  ├─ config = get_config(FileType.IMAGE)
  │   ├─ extensions = IMAGE_EXTENSIONS
  │   ├─ default_strategy = "newest"
  │   └─ display_name = "图片"
  └─ strategy = "newest" (smart → config.default_strategy)
  ↓
扫描阶段
  scan_files(dirs, extensions=config.extensions, ...)
  ↓
[photo1.jpg, photo2.png, photo3.jpg, photo1_copy.jpg, photo2_backup.png, ...]
  ↓
分组阶段（三阶段哈希）
  ├─ Stage 1: 按大小分组
  ├─ Stage 2: 按部分哈希分组（前64KB）
  └─ Stage 3: 按完整哈希分组
  ↓
find_duplicates(files, cache) →
[[photo1.jpg, photo1_copy.jpg], [photo2.png, photo2_backup.png]]
  ↓
选择阶段
  select_files_to_keep(groups, strategy="newest")
  ├─ 对每组：按 mtime 降序排序
  ├─ 保留最新的
  └─ 时间相近时 → 路径最短 → 字典序
  ↓
{photo1_copy.jpg: [photo1.jpg], photo2_backup.png: [photo2.png]}
  ↓
显示阶段
  ├─ 统计信息（使用 config.display_name）
  ├─ 策略说明
  └─ 确认提示
  ↓
删除阶段 (dry_run=True)
  delete_files(to_delete, dry_run=True)
  ↓
{"success": [], "failed": [], "skipped": [所有待删除文件]}
  ↓
日志记录
  create_deletion_log(cache_dir/logs, result, groups)
  ├─ file_type: "image"
  ├─ keep_strategy: "newest"
  └─ deleted_files: [...]
```

### 4.2 缓存交互

**缓存键设计**：
- 键: `(path, size, mtime)` 三元组
- 值: `(full_hash, partial_hash)`

**跨类型缓存**：
```
视频文件: /media/video.mp4 (100MB, mtime=1000) → hash=abc123
图片文件: /media/photo.jpg (5MB, mtime=2000) → hash=def456

缓存表:
| path              | size | mtime | full_hash |
|-------------------|------|-------|-----------|
| /media/video.mp4  | 100M | 1000  | abc123    |
| /media/photo.jpg  | 5M   | 2000  | def456    |

无冲突：路径不同自动区分
```

**缓存失效**：
- 文件修改（mtime 变化）→ 缓存未命中 → 重新计算
- 文件大小变化 → 缓存未命中
- 路径不变但内容变化 → 缓存命中（误报）→ **已接受的风险**（mtime 应该会变）

---

## 5. 错误处理

### 5.1 输入验证

**无效子命令**：
```bash
$ video-dedup photos ~/Photos
usage: video-dedup [-h] {video,image} ...
video-dedup: error: invalid choice: 'photos' (choose from 'video', 'image')
```
- argparse 自动处理

**无效策略**：
```bash
$ video-dedup image ~/Photos --keep-strategy random
usage: video-dedup image [-h] [--keep-strategy {oldest,newest,smart}] ...
video-dedup image: error: argument --keep-strategy: invalid choice: 'random'
```
- argparse choices 验证

**旧用法检测**：
```bash
$ video-dedup ~/Videos
错误：video-dedup v2.0 需要指定子命令

旧用法: video-dedup <目录>
新用法: video-dedup video <目录>
       video-dedup image <目录>

运行 'video-dedup --help' 查看详情
```
- main() 开头检测并友好提示

### 5.2 运行时错误

**目录不存在**：
```bash
$ video-dedup image /nonexistent
扫描目录:
  • /nonexistent

找到 0 个图片文件
未找到图片文件
```
- scanner 静默跳过无法访问的目录

**权限错误**：
```python
try:
    for entry in directory.iterdir():
        ...
except PermissionError:
    # 静默跳过无法访问的目录
    pass
```

**缓存损坏**：
- SQLite 自动处理（WAL 模式）
- 用户可通过 `--clear-cache` 重建

**删除失败**：
```python
result = delete_files(files)
# result["failed"] 包含失败的文件和错误信息
if result["failed"]:
    console.print(f"警告: {len(result['failed'])} 个文件删除失败")
    # 详细错误写入日志
```

### 5.3 边界情况

**空目录**：
```bash
$ video-dedup image ~/Empty
找到 0 个图片文件
未找到图片文件
```

**无重复**：
```bash
$ video-dedup video ~/Unique
找到 100 个视频文件
查找重复文件...

✓ 未发现重复视频
```

**混合文件类型**：
```bash
$ video-dedup image ~/Media  # 包含视频+图片
找到 50 个图片文件  # 自动过滤掉视频
发现 3 组重复图片
```
- scanner 按 extensions 过滤，自动忽略其他类型

---

## 6. 测试策略

### 6.1 测试结构

**新增测试文件**：
- `tests/test_file_types.py` - FileType 枚举和配置
- `tests/test_selector_strategies.py` - newest 策略测试
- `tests/test_cli_subcommands.py` - 子命令集成测试

**修改现有测试**：
- `tests/test_scanner.py` - 参数化（传入 extensions）
- `tests/test_utils.py` - 删除 VIDEO_EXTENSIONS 测试

**保持不变**：
- `tests/test_hasher.py` ✅
- `tests/test_cache.py` ✅
- `tests/test_grouper.py` ✅
- `tests/test_deleter.py` ✅

### 6.2 关键测试用例

#### 6.2.1 `test_file_types.py`（新增）

```python
def test_video_config():
    """测试视频配置"""
    from src.file_types import FileType, get_config
    
    config = get_config(FileType.VIDEO)
    
    assert '.mp4' in config.extensions
    assert '.mov' in config.extensions
    assert len(config.extensions) >= 20
    assert config.default_strategy == "oldest"
    assert config.display_name == "视频"

def test_image_config():
    """测试图片配置"""
    from src.file_types import FileType, get_config
    
    config = get_config(FileType.IMAGE)
    
    assert '.jpg' in config.extensions
    assert '.png' in config.extensions
    assert '.heic' in config.extensions
    assert len(config.extensions) >= 15
    assert config.default_strategy == "newest"
    assert config.display_name == "图片"

def test_config_immutability():
    """测试配置不可变"""
    from src.file_types import FileType, get_config
    
    config1 = get_config(FileType.VIDEO)
    config2 = get_config(FileType.VIDEO)
    
    # 应该返回相同的配置实例
    assert config1 is config2
```

#### 6.2.2 `test_selector_strategies.py`（新增）

```python
import time
import os

def test_select_newest_strategy(temp_dir, create_test_file):
    """测试 newest 策略保留最新文件"""
    from src.selector import select_files_to_keep
    
    # 创建3个相同内容的文件，不同时间
    file1 = create_test_file(temp_dir, "old.jpg", b"content")
    time.sleep(0.1)
    file2 = create_test_file(temp_dir, "mid.jpg", b"content")
    time.sleep(0.1)
    file3 = create_test_file(temp_dir, "new.jpg", b"content")
    
    selections = select_files_to_keep([[file1, file2, file3]], strategy="newest")
    
    # 应该保留最新的 file3
    assert file3 in selections
    assert set(selections[file3]) == {file1, file2}

def test_select_oldest_strategy_backward_compatible(temp_dir, create_test_file):
    """测试 oldest 策略向后兼容"""
    from src.selector import select_files_to_keep
    
    file1 = create_test_file(temp_dir, "old.mp4", b"content")
    time.sleep(0.1)
    file2 = create_test_file(temp_dir, "new.mp4", b"content")
    
    # 默认策略应该是 oldest
    selections = select_files_to_keep([[file1, file2]])
    
    assert file1 in selections
    assert selections[file1] == [file2]

def test_strategy_with_similar_time(temp_dir, create_test_file):
    """测试时间相近时的行为"""
    from src.selector import select_files_to_keep
    
    # 创建时间相近的文件
    file1 = create_test_file(temp_dir, "a/very/long/path/file.jpg", b"content")
    file2 = create_test_file(temp_dir, "short/file.jpg", b"content")
    
    # 设置相同的 mtime
    mtime = time.time()
    os.utime(file1, (mtime, mtime))
    os.utime(file2, (mtime, mtime))
    
    selections = select_files_to_keep([[file1, file2]], strategy="newest")
    
    # 应该保留路径更短的 file2
    assert file2 in selections
    assert selections[file2] == [file1]
```

#### 6.2.3 `test_scanner.py`（修改）

```python
def test_scan_with_custom_extensions(temp_dir, create_test_file):
    """测试自定义扩展名扫描"""
    from src.scanner import scan_files
    
    create_test_file(temp_dir, "video.mp4", b"video")
    create_test_file(temp_dir, "image.jpg", b"image")
    create_test_file(temp_dir, "doc.txt", b"doc")
    
    # 只扫描图片
    results = list(scan_files([temp_dir], extensions={'.jpg', '.png'}))
    
    assert len(results) == 1
    assert results[0].suffix == '.jpg'

def test_scan_case_insensitive_extensions(temp_dir, create_test_file):
    """测试扩展名大小写不敏感"""
    from src.scanner import scan_files
    
    create_test_file(temp_dir, "Photo.JPG", b"content")
    create_test_file(temp_dir, "photo.jpg", b"content")
    create_test_file(temp_dir, "PHOTO.jpg", b"content")
    
    results = list(scan_files([temp_dir], extensions={'.jpg'}))
    
    # 应该找到所有3个文件
    assert len(results) == 3
```

#### 6.2.4 `test_cli_subcommands.py`（新增）

```python
import subprocess
import sys

def test_video_subcommand_help():
    """测试 video 子命令帮助"""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli", "video", "--help"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert "视频文件去重" in result.stdout

def test_image_subcommand_help():
    """测试 image 子命令帮助"""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli", "image", "--help"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert "图片文件去重" in result.stdout

def test_video_subcommand_execution(temp_dir, create_test_file):
    """测试 video 子命令执行"""
    file1 = create_test_file(temp_dir, "a.mp4", b"content")
    file2 = create_test_file(temp_dir, "b.mp4", b"content")
    
    result = subprocess.run(
        [sys.executable, "-m", "src.cli", "video", str(temp_dir), "--dry-run"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert "视频" in result.stdout
    assert "重复" in result.stdout

def test_image_subcommand_execution(temp_dir, create_test_file):
    """测试 image 子命令执行"""
    file1 = create_test_file(temp_dir, "a.jpg", b"content")
    file2 = create_test_file(temp_dir, "b.jpg", b"content")
    
    result = subprocess.run(
        [sys.executable, "-m", "src.cli", "image", str(temp_dir), "--dry-run"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert "图片" in result.stdout
    assert "重复" in result.stdout

def test_old_usage_detection():
    """测试旧用法检测"""
    result = subprocess.run(
        [sys.executable, "-m", "src.cli", "/some/path"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 1
    assert "需要指定子命令" in result.stdout
    assert "新用法" in result.stdout

def test_strategy_parameter(temp_dir, create_test_file):
    """测试策略参数"""
    file1 = create_test_file(temp_dir, "a.jpg", b"content")
    file2 = create_test_file(temp_dir, "b.jpg", b"content")
    
    result = subprocess.run(
        [sys.executable, "-m", "src.cli", "image", str(temp_dir), 
         "--keep-strategy", "oldest", "--dry-run"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert "保留最早修改的文件" in result.stdout
```

### 6.3 测试覆盖率目标

- **代码覆盖率**: > 85%
- **分支覆盖率**: > 80%
- **关键路径**: 100%（扫描 → 分组 → 选择 → 删除）

### 6.4 测试数量预期

- 现有测试: 35个
- 新增测试: ~15个
  - file_types: 3个
  - selector_strategies: 3个
  - scanner (修改): 2个
  - cli_subcommands: 7个
- **总计: ~50个测试**

---

## 7. 实现细节

### 7.1 图片扩展名完整列表

```python
IMAGE_EXTENSIONS = {
    # 常见格式 (5种)
    '.jpg', '.jpeg',    # JPEG
    '.png',             # PNG
    '.gif',             # GIF
    '.bmp',             # Bitmap
    '.webp',            # WebP (Google)
    
    # RAW格式 (4种)
    '.raw',             # 通用RAW
    '.cr2',             # Canon RAW
    '.nef',             # Nikon RAW
    '.arw',             # Sony RAW
    
    # 其他格式 (6种)
    '.tiff', '.tif',    # TIFF
    '.heic', '.heif',   # HEIC (Apple)
    '.svg'              # SVG (矢量图)
}
# 总计: 15种格式
```

### 7.2 策略实现细节

**oldest 策略（现有逻辑，保持不变）**：
```python
# 1. 按 mtime 升序排序
sorted_files = sorted(group, key=lambda f: os.path.getmtime(f))

# 2. 选择最早的文件
oldest_file = sorted_files[0]
oldest_mtime = os.path.getmtime(oldest_file)

# 3. 找出时间相近的文件（<24h）
TIME_SIMILARITY_THRESHOLD = 86400  # 24小时
similar_time_files = [
    f for f in sorted_files
    if abs(os.path.getmtime(f) - oldest_mtime) < TIME_SIMILARITY_THRESHOLD
]

# 4. 如果有多个时间相近的，选路径最短的
if len(similar_time_files) > 1:
    to_keep = min(similar_time_files, key=lambda f: (len(str(f)), str(f)))
else:
    to_keep = oldest_file

# 5. 其余的都删除
to_delete = [f for f in group if f != to_keep]
```

**newest 策略（新增）**：
```python
# 1. 按 mtime 降序排序
sorted_files = sorted(group, key=lambda f: os.path.getmtime(f), reverse=True)

# 2. 选择最新的文件
newest_file = sorted_files[0]
newest_mtime = os.path.getmtime(newest_file)

# 3. 找出时间相近的文件（<24h）
similar_time_files = [
    f for f in sorted_files
    if abs(os.path.getmtime(f) - newest_mtime) < TIME_SIMILARITY_THRESHOLD
]

# 4-5. 后续逻辑与 oldest 相同
...
```

**代码复用**：
- 将共享逻辑提取为内部函数
- 只有排序方向不同

### 7.3 边界情况处理

**情况1：同名不同扩展名**
```
photo.jpg   (1MB, 2024-01-01)
photo.png   (1MB, 2024-01-01)  # 格式转换
```
- ✅ 如果内容完全相同（SHA-256匹配）→ 算重复
- ✅ 保留逻辑：时间相同 → 路径长度相同 → 字典序 → 保留 `photo.jpg`

**情况2：大小写敏感**
```
Photo.JPG
photo.jpg
PHOTO.jpg
```
- ✅ 扫描时 `.suffix.lower()` 统一转小写
- ✅ 所有变体都能识别

**情况3：HEIC vs JPG（iPhone导出）**
```
IMG_1234.HEIC  (原始，3MB)
IMG_1234.JPG   (导出，1MB)  # 不同内容
```
- ✅ 内容不同 → 不算重复
- ℹ️ 符合精确匹配的预期行为

**情况4：编辑过的图片**
```
original.jpg     (5MB, 2024-01-01)
original_edit.jpg (4MB, 2024-01-05)  # 裁剪/调色
```
- ✅ 内容不同 → 不算重复

**情况5：缩略图**
```
photo.jpg       (10MB, 高分辨率)
photo_thumb.jpg (100KB, 缩略图)
```
- ✅ 不算重复（字节不同）

### 7.4 日志格式扩展

**新增字段**：
```json
{
  "timestamp": "2026-10-06T10:30:00",
  "version": "2.0.0",
  "file_type": "image",           // 新增
  "keep_strategy": "newest",      // 新增
  "duplicate_groups": 3,
  "deleted_files": [...],
  "failed_deletions": [],
  "skipped_files": []
}
```

---

## 8. 向后兼容性

### 8.1 破坏性变更

**CLI 命令变更**：
- ❌ `video-dedup ~/Videos` 不再工作
- ✅ 必须使用 `video-dedup video ~/Videos`

**原因**：
- 子命令架构是必需的（清晰区分文件类型）
- 无法同时保持旧语法（会与新语法冲突）

### 8.2 迁移方案

**版本号升级**：
- v1.0.0 → v2.0.0（主版本号变更，遵循语义化版本）

**友好错误提示**：
```python
# main() 开头检测旧用法
if len(sys.argv) >= 2 and sys.argv[1] not in ['video', 'image', '-h', '--help']:
    potential_path = Path(sys.argv[1])
    if potential_path.exists():
        console.print("[red]错误：video-dedup v2.0 需要指定子命令[/red]")
        console.print("\n旧用法: video-dedup <目录>")
        console.print("新用法: video-dedup video <目录>")
        console.print("       video-dedup image <目录>")
        console.print("\n运行 'video-dedup --help' 查看详情")
        sys.exit(1)
```

**文档更新**：
- README 添加"从 v1.x 升级"章节
- CHANGELOG 明确标注破坏性变更
- GitHub Release 注释中强调

**迁移示例**：
```bash
# 旧版本 (v1.0.0)
video-dedup ~/Videos --dry-run

# 新版本 (v2.0.0)
video-dedup video ~/Videos --dry-run
```

### 8.3 数据兼容性

**缓存数据库**：
- ✅ 完全向后兼容
- 现有缓存继续工作
- 新缓存条目（图片）自然添加

**日志文件**：
- ✅ 旧日志可读
- 新日志添加 `file_type` 和 `keep_strategy` 字段
- 旧日志缺少这些字段，解析时提供默认值

---

## 9. 性能分析

### 9.1 性能影响

**无性能退化**：
- 哈希算法不变（SHA-256）
- 缓存机制不变
- 三阶段分组逻辑不变

**理论性能**：
- 视频扫描：与 v1.0.0 完全相同
- 图片扫描：可能更快（文件通常更小）

### 9.2 基准测试计划

**测试场景**：
- 3000 个视频文件（总大小 900GB）
- 5000 个图片文件（总大小 50GB）

**预期结果**：
- 视频首次扫描: 5-10 分钟（与 v1.0 相同）
- 视频增量扫描: < 2 分钟（与 v1.0 相同）
- 图片首次扫描: 2-5 分钟（更快，文件小）
- 图片增量扫描: < 1 分钟（更快）

### 9.3 优化机会（未来）

**当前不实现，未来可考虑**：
- 图片可能更小，考虑更大的 `PARTIAL_HASH_SIZE`（当前 64KB）
- 并行哈希计算（当前单线程）
- 进度条显示（当前无）

---

## 10. 部署计划

### 10.1 发布步骤

1. **开发分支**: `feature/image-dedup`
2. **测试**: 确保 50 个测试全部通过
3. **文档更新**:
   - README: 添加图片去重示例
   - CHANGELOG: 详细记录 v2.0.0 变更
   - 迁移指南: 从 v1.x 升级说明
4. **版本升级**: `pyproject.toml` version = "2.0.0"
5. **Git 标签**: `git tag v2.0.0`
6. **GitHub Release**: 
   - 标题: "v2.0.0 - 图片去重支持"
   - 说明: 破坏性变更 + 迁移指南
7. **推送**: `git push origin main --tags`

### 10.2 回滚计划

如果发现严重问题：
```bash
git revert <commit-range>
git tag v2.0.1  # 修复版本
git push origin main --tags
```

### 10.3 用户沟通

**GitHub Release 模板**：
```markdown
## v2.0.0 - 图片去重支持 🎉

### ⚠️ 破坏性变更

video-dedup v2.0 引入了子命令架构。旧的命令行语法不再支持。

**旧版本 (v1.x)**:
```bash
video-dedup ~/Videos
```

**新版本 (v2.0)**:
```bash
video-dedup video ~/Videos
video-dedup image ~/Photos
```

### ✨ 新功能

- 🖼️ **图片去重**: 支持 15 种图片格式（.jpg, .png, .heic, .raw, 等）
- 🎯 **智能保留策略**: 
  - 视频默认保留最早的文件（原始录制）
  - 图片默认保留最新的文件（编辑后版本）
- 🔧 **手动策略覆盖**: `--keep-strategy oldest|newest|smart`

### 🔧 改进

- 代码架构重构，易于扩展新文件类型
- 更清晰的错误提示
- 完善的测试覆盖（50 个测试用例）

### 📚 文档

- [迁移指南](docs/migration-v1-to-v2.md)
- [使用示例](README.md#使用方法)

### 🙏 感谢

感谢所有使用 video-dedup 的用户！
```

---

## 11. 未来扩展

### 11.1 短期扩展（v2.1 - v2.3）

**音频去重**（v2.1）：
```python
FileType.AUDIO = "audio"
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.wav', '.m4a', '.aac', ...}
# 复用所有现有逻辑
```

**进度条**（v2.2）：
```python
from rich.progress import Progress
with Progress() as progress:
    task = progress.add_task("扫描文件...", total=len(files))
    ...
```

**并行哈希**（v2.3）：
```python
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=8) as executor:
    hashes = list(executor.map(compute_full_hash, files))
```

### 11.2 中期扩展（v3.0）

**配置文件支持**：
```yaml
# ~/.video-dedup/config.yaml
defaults:
  video:
    strategy: oldest
  image:
    strategy: newest
    
exclude:
  - "iMovie 项目"
  - "Final Cut"
```

**插件系统**：
```python
# 用户自定义文件类型
class DocumentType(MediaType):
    extensions = {'.pdf', '.docx'}
    default_strategy = "newest"
```

### 11.3 长期扩展（v4.0+）

**感知哈希（可选）**：
```bash
video-dedup image ~/Photos --mode perceptual --threshold 5
```

**Web UI**：
```bash
video-dedup serve --port 8080
# 浏览器打开 http://localhost:8080
```

**云存储支持**：
```bash
video-dedup image s3://my-bucket/photos
```

---

## 12. 风险评估

### 12.1 技术风险

| 风险 | 可能性 | 影响 | 缓解措施 |
|-----|-------|-----|---------|
| 现有测试失败 | 中 | 高 | 谨慎重构，保持接口不变 |
| 性能退化 | 低 | 中 | 核心算法不变，加基准测试 |
| 缓存冲突 | 低 | 低 | 缓存键基于路径，天然隔离 |
| CLI 迁移困难 | 高 | 中 | 友好错误提示 + 详细文档 |

### 12.2 用户体验风险

| 风险 | 可能性 | 影响 | 缓解措施 |
|-----|-------|-----|---------|
| 用户不知道子命令 | 高 | 中 | 旧用法检测 + 提示 |
| 策略混淆 | 中 | 低 | 清晰的帮助文档 |
| 破坏性升级不满 | 中 | 中 | v2.0.0 标注，详细迁移指南 |

### 12.3 开发风险

| 风险 | 可能性 | 影响 | 缓解措施 |
|-----|-------|-----|---------|
| 实现超出预期时间 | 中 | 低 | 分阶段实现，最小可行产品 |
| 测试覆盖不足 | 低 | 高 | 50 个测试用例，>85% 覆盖率 |
| 文档过时 | 中 | 中 | 代码和文档同步更新 |

---

## 13. 成功标准

### 13.1 功能完整性

- ✅ 用户可以通过 `video-dedup image ~/Photos` 去重图片
- ✅ 用户可以通过 `video-dedup video ~/Videos` 去重视频
- ✅ 支持 15+ 种图片格式
- ✅ 智能保留策略正确工作（视频 oldest，图片 newest）
- ✅ 所有现有功能（缓存、dry-run、排除规则）对两种文件类型都有效
- ✅ 旧用法有友好错误提示

### 13.2 质量标准

- ✅ 所有 50 个测试通过
- ✅ 代码覆盖率 > 85%
- ✅ 无性能退化（基准测试验证）
- ✅ 文档完整（README + CHANGELOG + 迁移指南）

### 13.3 用户验收标准

**场景1：视频去重**
```bash
$ video-dedup video ~/Videos --dry-run
找到 100 个视频文件
发现 5 组重复视频
保留策略：保留最早修改的文件
```

**场景2：图片去重**
```bash
$ video-dedup image ~/Photos --dry-run
找到 500 个图片文件
发现 10 组重复图片
保留策略：保留最新修改的文件
```

**场景3：策略覆盖**
```bash
$ video-dedup image ~/Archive --keep-strategy oldest --dry-run
找到 200 个图片文件
发现 3 组重复图片
保留策略：保留最早修改的文件  # 覆盖了默认的 newest
```

**场景4：混合目录**
```bash
$ video-dedup image ~/Media  # 包含视频和图片
找到 50 个图片文件  # 自动过滤掉视频
```

---

## 14. 实现工作量估算

### 14.1 开发任务分解

| 任务 | 预估时间 | 优先级 |
|-----|---------|-------|
| 创建 file_types.py | 1 小时 | P0 |
| 修改 scanner.py | 0.5 小时 | P0 |
| 修改 selector.py | 1 小时 | P0 |
| 重构 cli.py | 3 小时 | P0 |
| 修改 utils.py | 0.5 小时 | P0 |
| 编写新测试 | 2 小时 | P0 |
| 修改现有测试 | 1 小时 | P0 |
| 更新文档 | 1 小时 | P0 |
| 手动测试 | 1 小时 | P1 |
| Code Review | 1 小时 | P1 |

**总计**: ~12 小时（1.5 个工作日）

### 14.2 里程碑

**Milestone 1: 核心功能**（Day 1 上午）
- ✅ file_types.py 完成
- ✅ scanner.py 参数化
- ✅ selector.py 策略支持

**Milestone 2: CLI 重构**（Day 1 下午）
- ✅ cli.py 子命令架构
- ✅ 旧用法检测

**Milestone 3: 测试和文档**（Day 2 上午）
- ✅ 所有测试通过
- ✅ 文档更新

**Milestone 4: 发布**（Day 2 下午）
- ✅ 手动验证
- ✅ 打标签发布

---

## 15. 附录

### 15.1 参考资料

- [SHA-256 规范](https://en.wikipedia.org/wiki/SHA-2)
- [argparse 子命令](https://docs.python.org/3/library/argparse.html#sub-commands)
- [语义化版本](https://semver.org/lang/zh-CN/)
- [Rich 库文档](https://rich.readthedocs.io/)

### 15.2 术语表

| 术语 | 定义 |
|-----|------|
| 精确匹配 | 基于字节级 SHA-256 哈希的重复检测 |
| 感知哈希 | 基于视觉相似度的哈希（本版本不支持）|
| 保留策略 | 决定在重复组中保留哪个文件的规则 |
| 子命令 | CLI 的第一个位置参数，决定操作类型 |
| 智能策略 | 根据文件类型自动选择保留策略 |
| 破坏性变更 | 不向后兼容的 API 变更 |

### 15.3 设计决策记录

**决策1：为什么选择最小抽象层而非领域模型？**
- 理由：当前只有 2 种文件类型，YAGNI 原则
- 权衡：未来如果超过 5 种类型，可能需要重构为领域模型
- 日期：2026-10-06

**决策2：为什么图片默认保留 newest？**
- 理由：图片通常编辑后导出，最新版本通常质量更好
- 权衡：可能不适合历史照片归档场景（用户可覆盖）
- 日期：2026-10-06

**决策3：为什么不支持统一扫描模式？**
- 理由：简化实现，独立命令更清晰
- 权衡：需要多次扫描混合目录（未来可添加）
- 日期：2026-10-06

**决策4：为什么是破坏性升级（v2.0）？**
- 理由：子命令架构无法与旧语法兼容
- 权衡：用户需要修改脚本，但长期更清晰
- 日期：2026-10-06

---

## 16. 审阅清单

### 16.1 设计审阅

- [ ] 架构清晰，模块职责明确
- [ ] 接口设计合理，易于扩展
- [ ] 错误处理完善
- [ ] 性能考虑充分
- [ ] 测试策略完整

### 16.2 实现审阅

- [ ] 代码符合现有风格
- [ ] 类型注解完整
- [ ] 文档字符串清晰
- [ ] 无硬编码魔法值
- [ ] 日志记录恰当

### 16.3 文档审阅

- [ ] README 更新完整
- [ ] CHANGELOG 记录详细
- [ ] 迁移指南清晰
- [ ] 代码注释充分
- [ ] 示例代码正确

---

**文档结束**

**下一步**: 使用 `superpowers:writing-plans` 技能创建实现计划。
