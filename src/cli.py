"""Command-line interface for video-dedup."""
import sys
import argparse
from pathlib import Path
from rich.console import Console
from rich.progress import Progress
from src.scanner import scan_files
from src.grouper import find_duplicates
from src.selector import select_files_to_keep
from src.deleter import delete_files, create_deletion_log
from src.cache import Cache
from src.utils import format_size, format_duration
import time

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

if __name__ == "__main__":
    main()
