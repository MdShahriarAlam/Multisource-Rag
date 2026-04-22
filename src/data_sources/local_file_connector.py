"""Local filesystem connector for user-uploaded documents."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import settings
from ..errors import FileNotFound, PathTraversal
from .base import StorageConnector
from .registry import register

log = logging.getLogger(__name__)


@register("local_file")
class LocalFileConnector(StorageConnector):
    """Connector for a local upload folder (default: uploaded_files/)."""

    source_type = "local_file"
    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv", ".xlsx", ".json"}

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        configured = config.get("upload_dir") or settings.upload_dir
        self.upload_dir = Path(configured).resolve()

    async def connect(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def disconnect(self) -> None:
        return None

    async def health_check(self) -> bool:
        return self.upload_dir.exists() and self.upload_dir.is_dir()

    def _resolve_safe(self, file_path: str) -> Path:
        """Resolve ``file_path`` inside ``upload_dir``. Rejects traversal."""
        if not file_path:
            raise PathTraversal("Empty file path")
        # Reject anything with separators or parent refs — basename only
        base = Path(file_path).name
        if base != file_path or base in ("", ".", "..") or ".." in base:
            raise PathTraversal(
                "File path must be a bare filename inside the upload dir",
                details={"file_path": file_path},
            )
        candidate = (self.upload_dir / base).resolve()
        try:
            candidate.relative_to(self.upload_dir)
        except ValueError as e:
            raise PathTraversal(
                "Path escapes upload directory",
                details={"file_path": file_path},
            ) from e
        return candidate

    async def list_files(
        self,
        prefix: str = "",
        extensions: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        if not self.upload_dir.exists():
            await self.connect()

        allowed_ext = {e.lower() for e in (extensions or self.SUPPORTED_EXTENSIONS)}
        loop = asyncio.get_running_loop()

        def _list() -> List[Dict[str, Any]]:
            files: List[Dict[str, Any]] = []
            try:
                entries = sorted(self.upload_dir.iterdir())
            except FileNotFoundError:
                return files
            for path in entries:
                if not path.is_file():
                    continue
                if path.suffix.lower() not in allowed_ext:
                    continue
                if prefix and not path.name.startswith(prefix):
                    continue
                try:
                    stat = path.stat()
                except OSError:
                    continue
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
        target = self._resolve_safe(file_path)
        if not target.exists() or not target.is_file():
            raise FileNotFound(f"File '{target.name}' not found")
        if target.stat().st_size > settings.max_file_bytes:
            raise PathTraversal(
                "File exceeds max_file_bytes",
                details={
                    "file_path": file_path,
                    "size": target.stat().st_size,
                    "max_bytes": settings.max_file_bytes,
                },
            )
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, target.read_bytes)

    async def get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        target = self._resolve_safe(file_path)
        if not target.exists() or not target.is_file():
            raise FileNotFound(f"File '{target.name}' not found")
        stat = target.stat()
        return {
            "name": target.name,
            "size": stat.st_size,
            "last_modified": datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat(),
            "content_type": None,
        }
