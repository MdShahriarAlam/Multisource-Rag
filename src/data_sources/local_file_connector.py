"""Local filesystem connector for user-uploaded documents."""
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import StorageConnector
from .registry import register


@register("local_file")
class LocalFileConnector(StorageConnector):
    """Connector for a local upload folder (uploaded_files/)."""

    source_type = "local_file"
    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv", ".xlsx", ".json"}

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.upload_dir = Path(config.get("upload_dir", "./uploaded_files"))

    async def connect(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def disconnect(self) -> None:
        pass  # no persistent connection to close

    async def list_files(
        self,
        prefix: str = "",
        extensions: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """List files in the upload directory."""
        if not self.upload_dir.exists():
            await self.connect()

        allowed_ext = set(extensions) if extensions else self.SUPPORTED_EXTENSIONS
        loop = asyncio.get_event_loop()

        def _list() -> List[Dict[str, Any]]:
            files = []
            for path in sorted(self.upload_dir.iterdir()):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in allowed_ext:
                    continue
                if prefix and not path.name.startswith(prefix):
                    continue
                stat = path.stat()
                last_modified = datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat()
                files.append(
                    {
                        "name": path.name,
                        "size": stat.st_size,
                        "last_modified": last_modified,
                        "content_type": None,
                    }
                )
            return files

        return await loop.run_in_executor(None, _list)

    async def download_file(self, file_path: str) -> bytes:
        """Read a file from the upload directory and return its bytes."""
        loop = asyncio.get_event_loop()
        full_path = self.upload_dir / file_path

        def _read() -> bytes:
            return full_path.read_bytes()

        return await loop.run_in_executor(None, _read)

    async def get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """Return metadata for a file in the upload directory."""
        loop = asyncio.get_event_loop()
        full_path = self.upload_dir / file_path

        def _meta() -> Dict[str, Any]:
            stat = full_path.stat()
            return {
                "name": full_path.name,
                "size": stat.st_size,
                "last_modified": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(),
                "content_type": None,
            }

        return await loop.run_in_executor(None, _meta)
