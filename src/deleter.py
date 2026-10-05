"""Safe file deletion via system trash."""
from pathlib import Path
from send2trash import send2trash
import json
from datetime import datetime

def delete_files(files: list[Path], dry_run: bool = False) -> dict[str, any]:
    """
    Delete files by moving to system trash.

    Args:
        files: List of files to delete
        dry_run: If True, don't actually delete

    Returns:
        Dictionary with success, failed, and skipped lists
    """
    result = {
        "success": [],
        "failed": [],
        "skipped": []
    }

    if dry_run:
        result["skipped"] = [str(f) for f in files]
        return result

    for file_path in files:
        try:
            send2trash(str(file_path))
            result["success"].append(str(file_path))
        except Exception as e:
            result["failed"].append({"path": str(file_path), "error": str(e)})

    return result

def create_deletion_log(log_dir: Path, deletion_result: dict, duplicate_groups: list) -> Path:
    """
    Create JSON log of deletion operation.

    Args:
        log_dir: Directory to store log files
        deletion_result: Result from delete_files
        duplicate_groups: Original duplicate groups

    Returns:
        Path to created log file
    """
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now()
    log_filename = timestamp.strftime("%Y-%m-%d_%H%M%S.log")
    log_path = log_dir / log_filename

    log_data = {
        "timestamp": timestamp.isoformat(),
        "version": "1.0.0",
        "duplicate_groups": len(duplicate_groups),
        "deleted_files": deletion_result["success"],
        "failed_deletions": deletion_result["failed"],
        "skipped_files": deletion_result["skipped"]
    }

    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

    return log_path
