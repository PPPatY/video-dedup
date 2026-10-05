import pytest


def test_cli_rejects_non_positive_thread_count():
    from src.cli import create_parser

    with pytest.raises(SystemExit) as exc_info:
        create_parser().parse_args(["video", ".", "--threads", "0"])

    assert exc_info.value.code == 2


def test_cli_rejects_missing_scan_directory(tmp_path, monkeypatch):
    from src.cli import main

    missing_dir = tmp_path / "missing"
    monkeypatch.setattr(
        "sys.argv",
        ["video-dedup", "video", str(missing_dir), "--cache-dir", str(tmp_path / "cache")],
    )

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 2
    assert not (tmp_path / "cache").exists()
