"""Path traversal rejection on local_file_connector + upload."""
import tempfile
from pathlib import Path

import pytest

from src.data_sources.local_file_connector import LocalFileConnector
from src.errors import PathTraversal


@pytest.fixture
def connector(tmp_path):
    return LocalFileConnector("local_uploads", {"upload_dir": str(tmp_path)})


@pytest.mark.parametrize(
    "bad",
    [
        "../etc/passwd",
        "..\\windows\\system32\\cmd.exe",
        "subdir/file.txt",
        "/absolute/path.txt",
        "C:\\windows\\system32.txt",
        "..",
        ".",
        "",
        "foo/../bar.txt",
    ],
)
@pytest.mark.asyncio
async def test_download_rejects_traversal(connector, bad):
    with pytest.raises(PathTraversal):
        await connector.download_file(bad)


@pytest.mark.asyncio
async def test_download_valid_filename(connector, tmp_path):
    target = tmp_path / "ok.txt"
    target.write_bytes(b"hello")
    content = await connector.download_file("ok.txt")
    assert content == b"hello"


@pytest.mark.asyncio
async def test_health_check(connector):
    await connector.connect()
    assert await connector.health_check() is True
