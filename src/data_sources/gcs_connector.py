"""Google Cloud Storage connector for document/file retrieval."""
import asyncio
from typing import Any, Dict, List, Optional

from google.cloud import storage
from google.oauth2 import service_account

from .base import StorageConnector
from .registry import register


@register("gcs")
class GCSConnector(StorageConnector):
    """Connector for Google Cloud Storage."""

    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv", ".xlsx", ".json"}

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.client = None
        self.bucket = None
        self.bucket_name = config.get("bucket", "")

    async def connect(self) -> None:
        """Establish connection to GCS."""
        loop = asyncio.get_event_loop()

        def _connect():
            credentials = service_account.Credentials.from_service_account_file(
                self.config["credentials_file"]
            )
            self.client = storage.Client(
                credentials=credentials,
                project=self.config.get("project_id"),
            )
            self.bucket = self.client.bucket(self.bucket_name)

        await loop.run_in_executor(None, _connect)

    async def disconnect(self) -> None:
        """Close GCS connection."""
        if self.client:
            self.client.close()
            self.client = None
            self.bucket = None

    async def list_files(
        self,
        prefix: str = "",
        extensions: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """List objects in the bucket, optionally filtered."""
        if not self.client:
            await self.connect()

        allowed_ext = (
            set(extensions) if extensions else self.SUPPORTED_EXTENSIONS
        )
        loop = asyncio.get_event_loop()

        def _list():
            files = []
            blobs = self.client.list_blobs(
                self.bucket_name, prefix=prefix or None
            )
            for blob in blobs:
                ext = (
                    "." + blob.name.rsplit(".", 1)[-1].lower()
                    if "." in blob.name
                    else ""
                )
                if ext in allowed_ext:
                    files.append(
                        {
                            "name": blob.name,
                            "size": blob.size,
                            "last_modified": blob.updated.isoformat()
                            if blob.updated
                            else None,
                            "content_type": blob.content_type,
                        }
                    )
            return files

        return await loop.run_in_executor(None, _list)

    async def download_file(self, file_path: str) -> bytes:
        """Download an object and return its content."""
        if not self.bucket:
            await self.connect()

        loop = asyncio.get_event_loop()

        def _download():
            blob = self.bucket.blob(file_path)
            return blob.download_as_bytes()

        return await loop.run_in_executor(None, _download)

    async def get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """Get metadata for a specific object."""
        if not self.bucket:
            await self.connect()

        loop = asyncio.get_event_loop()

        def _metadata():
            blob = self.bucket.get_blob(file_path)
            if not blob:
                raise FileNotFoundError(f"Object not found: {file_path}")
            return {
                "name": blob.name,
                "size": blob.size,
                "content_type": blob.content_type,
                "last_modified": blob.updated.isoformat()
                if blob.updated
                else None,
                "etag": blob.etag,
            }

        return await loop.run_in_executor(None, _metadata)
