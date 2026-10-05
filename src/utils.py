"""Utility functions and constants."""

def format_size(bytes: int) -> str:
    """Format bytes as human-readable size (e.g., '1.2 GB')."""
    if bytes < 1024:
        return f"{bytes} B"
    elif bytes < 1024 ** 2:
        return f"{bytes / 1024:.1f} KB"
    elif bytes < 1024 ** 3:
        return f"{bytes / (1024 ** 2):.1f} MB"
    else:
        return f"{bytes / (1024 ** 3):.1f} GB"

def format_duration(seconds: float) -> str:
    """Format seconds as human-readable duration (e.g., '5 分 32 秒')."""
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours} 小时 {minutes} 分 {secs} 秒"
    elif minutes > 0:
        return f"{minutes} 分 {secs} 秒"
    else:
        return f"{secs} 秒"
