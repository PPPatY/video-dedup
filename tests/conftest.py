import tempfile
import os
from pathlib import Path
import pytest

@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def create_test_file():
    """Factory fixture to create test files with specific content."""
    def _create(parent_dir: Path, filename: str, content: bytes) -> Path:
        file_path = parent_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)
        return file_path
    return _create
