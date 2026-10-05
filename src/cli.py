"""Command-line interface for video-dedup (video / image subcommands).

[INPUT]: depends on file_types for per-type config, scanner for discovery, grouper for duplicate detection,
         selector for retention strategy, deleter for safe deletion, cache for hash cache, utils for formatting
[OUTPUT]: exports create_parser, process_dedup, main
[POS]: application entry point; `video-dedup video|image <dirs>` shares one dedup workflow (process_dedup)
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
import sys
import argparse
import time
from pathlib import Path
from rich.console import Console

from src.file_types import FileType, get_config
from src.scanner import scan_files
from src.grouper import find_duplicates
from src.selector import select_files_to_keep
from src.deleter import delete_files, create_deletion_log
from src.cache import Cache
from src.utils import format_size, format_duration

console = Console()

SUBCOMMANDS = {
    "video": (FileType.VIDEO, "视频文件去重"),
    "image": (FileType.IMAGE, "图片文件去重"),
}

STRATEGY_DESC = {
    "oldest": "保留最早修改的文件",
    "newest": "保留最新修改的文件",
}


def _positive_int(value: str) -> int:
    """Parse a positive integer for resource-related CLI options."""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("必须是整数") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("必须大于 0")
    return parsed


def _add_common_args(subparser: argparse.ArgumentParser) -> None:
    """Register options shared by every subcommand."""
    subparser.add_argument("directories", nargs="+", type=Path, help="要扫描的目录")
    subparser.add_argument("--exclude", nargs="+", default=[], help="排除的目录名称")
    subparser.add_argument("--dry-run", action="store_true", help="预览模式，不实际删除")
    subparser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path.home() / ".video-dedup",
        help="缓存目录（默认 ~/.video-dedup）",
    )
    subparser.add_argument("--clear-cache", action="store_true", help="清空缓存")
    subparser.add_argument(
        "--threads", type=_positive_int, default=8, help="并发线程数（默认 8）"
    )
    subparser.add_argument(
        "--keep-strategy",
        choices=["oldest", "newest", "smart"],
        default="smart",
        help="保留策略：oldest=最早 newest=最新 smart=根据文件类型自动选择（默认）",
    )
    subparser.add_argument("--follow-symlinks", action="store_true", help="跟随符号链接")
    subparser.add_argument("--include-hidden", action="store_true", help="包含隐藏文件")


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser with video/image subcommands."""
    parser = argparse.ArgumentParser(prog="video-dedup", description="通用媒体文件去重工具")
    subparsers = parser.add_subparsers(dest="command", required=True, help="操作类型")

    for name, (_, description) in SUBCOMMANDS.items():
        sub = subparsers.add_parser(name, help=description, description=description)
        _add_common_args(sub)

    return parser


def _validate_directories(directories: list[Path]) -> None:
    invalid = [d for d in directories if not d.exists() or not d.is_dir()]
    if invalid:
        details = ", ".join(str(d) for d in invalid)
        console.print(f"[red]错误: 扫描目录不存在或不是目录: {details}[/red]")
        sys.exit(2)


def _print_summary(args, config, strategy, files, groups, total_duplicates, total_size, cache, elapsed):
    console.print("\n" + "=" * 50)
    console.print(f"[green]✓ 扫描完成[/green] (用时 {format_duration(elapsed)})")
    console.print("\n📊 统计:")
    console.print(f"  • 总文件数: {len(files)} 个{config.display_name}")
    console.print(f"  • 发现重复: {len(groups)} 组（{total_duplicates} 个文件可删除）")
    console.print(f"  • 可释放空间: {format_size(total_size)}")

    if cache:
        stats = cache.get_stats()
        if stats["hit_count"] + stats["miss_count"] > 0:
            hit_rate = stats["hit_count"] / (stats["hit_count"] + stats["miss_count"])
            console.print(f"  • 缓存命中率: {hit_rate:.1%}")

    console.print("\n🗑️  删除策略:")
    console.print(f"  • {STRATEGY_DESC[strategy]}")
    console.print("  • 时间相近时保留路径最短的")


def _confirm_and_delete(args, selections, groups, total_duplicates, total_size) -> None:
    all_to_delete = [f for to_delete in selections.values() for f in to_delete]

    if args.dry_run:
        console.print("\n[yellow]⚠️  预览模式（--dry-run）：不会实际删除文件[/yellow]")
        log_path = create_deletion_log(
            args.cache_dir / "logs",
            {"success": [], "failed": [], "skipped": [str(f) for f in all_to_delete]},
            groups,
        )
        console.print(f"删除计划已保存到: {log_path}")
        return

    console.print(f"\n确认删除 {total_duplicates} 个重复文件？[y/N] ", end="")
    try:
        response = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        response = ""

    if response != "y":
        console.print("\n取消操作")
        return

    result = delete_files(all_to_delete)
    console.print("\n[green]✓ 操作完成[/green]")
    console.print(f"  • 已删除: {len(result['success'])} 个文件")
    console.print(f"  • 已释放: {format_size(total_size)}")
    console.print("  • 文件已移至回收站（可在“废纸篓”中恢复）")

    log_path = create_deletion_log(args.cache_dir / "logs", result, groups)
    console.print(f"  • 操作日志: {log_path}")

    if result["failed"]:
        console.print(f"\n[yellow]警告: {len(result['failed'])} 个文件删除失败（详见日志）[/yellow]")


def process_dedup(args, file_type: FileType) -> None:
    """Shared dedup workflow for every file type."""
    config = get_config(file_type)
    strategy = config.default_strategy if args.keep_strategy == "smart" else args.keep_strategy

    _validate_directories(args.directories)

    console.print(f"[green]🔍 扫描{config.display_name}文件...[/green]\n")

    cache = None
    if args.cache_dir:
        cache = Cache(args.cache_dir)
        if args.clear_cache:
            console.print("清空缓存...")
            cache.clear()

    console.print("扫描目录:")
    for directory in args.directories:
        console.print(f"  • {directory}")

    if args.exclude:
        console.print("排除规则:")
        for pattern in args.exclude:
            console.print(f"  • {pattern}")

    start_time = time.time()

    files = list(scan_files(
        args.directories,
        extensions=config.extensions,
        exclude_patterns=args.exclude,
        follow_symlinks=args.follow_symlinks,
        include_hidden=args.include_hidden,
    ))

    if not files:
        console.print(f"\n[yellow]未找到{config.display_name}文件[/yellow]")
        sys.exit(0)

    console.print(f"\n找到 {len(files)} 个{config.display_name}文件")

    console.print("查找重复文件...")
    groups = find_duplicates(files, cache=cache, workers=args.threads)

    if not groups:
        console.print(f"\n[green]✓ 未发现重复{config.display_name}[/green]")
        sys.exit(0)

    selections = select_files_to_keep(groups, strategy=strategy)
    total_duplicates = sum(len(to_delete) for to_delete in selections.values())
    total_size = sum(f.stat().st_size for to_delete in selections.values() for f in to_delete)

    _print_summary(
        args, config, strategy, files, groups, total_duplicates, total_size,
        cache, time.time() - start_time,
    )
    _confirm_and_delete(args, selections, groups, total_duplicates, total_size)
    sys.exit(0)


def _reject_legacy_usage(argv: list[str]) -> None:
    """v1.x took directories directly; point those users at the new syntax."""
    if len(argv) < 2 or argv[1] in SUBCOMMANDS or argv[1].startswith("-"):
        return
    if Path(argv[1]).exists():
        console.print("[red]错误：video-dedup v2.0 需要指定子命令[/red]", highlight=False)
        console.print("\n旧用法: video-dedup <目录>", highlight=False)
        console.print("新用法: video-dedup video <目录>", highlight=False)
        console.print("       video-dedup image <目录>", highlight=False)
        console.print("\n运行 'video-dedup --help' 查看详情", highlight=False)
        sys.exit(1)


def main():
    """Main entry point."""
    _reject_legacy_usage(sys.argv)
    args = create_parser().parse_args()
    process_dedup(args, SUBCOMMANDS[args.command][0])


if __name__ == "__main__":
    main()
