import json


def test_delete_files_dry_run_does_not_remove_files(temp_dir, create_test_file):
    from src.deleter import delete_files

    file_path = create_test_file(temp_dir, "video.mp4", b"content")

    result = delete_files([file_path], dry_run=True)

    assert result == {
        "success": [],
        "failed": [],
        "skipped": [str(file_path)],
    }
    assert file_path.exists()


def test_create_deletion_log_writes_structured_result(temp_dir):
    from src.deleter import create_deletion_log

    result = {
        "success": ["/tmp/removed.mp4"],
        "failed": [{"path": "/tmp/failed.mp4", "error": "denied"}],
        "skipped": ["/tmp/skipped.mp4"],
    }
    log_path = create_deletion_log(temp_dir / "logs", result, [["a", "b"]])

    assert log_path.parent == temp_dir / "logs"
    assert log_path.suffix == ".log"
    with log_path.open(encoding="utf-8") as log_file:
        data = json.load(log_file)

    assert data["duplicate_groups"] == 1
    assert data["deleted_files"] == result["success"]
    assert data["failed_deletions"] == result["failed"]
    assert data["skipped_files"] == result["skipped"]
