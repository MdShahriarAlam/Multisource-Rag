"""Azure Blob Storage connector for document/file retrieval."""
import asyncio
from typing import Any, Dict, List, Optional

from azure.storage.blob import BlobServiceClient

from .base import StorageConnector
from .registry import register


@register("azure_blob")
class AzureBlobConnector(StorageConnector):
    """Connector for Azure Blob Storage."""

    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv", ".xlsx", ".json"}

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.blob_service_client = None
        self.container_client = None
        self.container_name = config.get("container_name", "documents")

    async def connect(self) -> None:
        """Establish connection to Azure Blob Storage."""
        loop = asyncio.get_event_loop()

        def _connect():
            self.blob_service_client = BlobServiceClient.from_connection_string(
                self.config["connection_string"]
            )
            self.container_client = self.blob_service_client.get_container_client(
                self.container_name
            )

        await loop.run_in_executor(None, _connect)

    async def disconnect(self) -> None:
        """Close Azure Blob Storage connection."""
        if self.blob_service_client:
            self.blob_service_client.close()
            self.blob_service_client = None
            self.container_client = None

    async def list_files(
        self,
        prefix: str = "",
        extensions: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """List blobs in the container, optionally filtered."""
        if not self.container_client:
            await self.connect()

        allowed_ext = (
            set(extensions) if extensions else self.SUPPORTED_EXTENSIONS
        )
        loop = asyncio.get_event_loop()

        def _list():
            files = []
            for blob in self.container_client.list_blobs(name_starts_with=prefix or None):
                ext = "." + blob.name.rsplit(".", 1)[-1].lower() if "." in blob.name else ""
                if ext in allowed_ext:
                    files.append(
                        {
                            "name": blob.name,
                            "size": blob.size,
                            "last_modified": blob.last_modified.isoformat()
                            if blob.last_modified
                            else None,
                            "content_type": blob.content_settings.content_type
                            if blob.content_settings
                            else None,
                        }
                    )
            return files

        return await loop.run_in_executor(None, _list)

    async def download_file(self, file_path: str) -> bytes:
        """Download a blob and return its content."""
        if not self.container_client:
            await self.connect()

        loop = asyncio.get_event_loop()

        def _download():
            blob_client = self.container_client.get_blob_client(file_path)
            return blob_client.download_blob().readall()

        return await loop.run_in_executor(None, _download)

    async def get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """Get metadata for a specific blob."""
        if not self.container_client:
            await self.connect()

        loop = asyncio.get_event_loop()

        def _metadata():
            blob_client = self.container_client.get_blob_client(file_path)
            props = blob_client.get_blob_properties()
            return {
                "name": props.name,
                "size": props.size,
                "content_type": props.content_settings.content_type
                if props.content_settings
                else None,
                "last_modified": props.last_modified.isoformat()
                if props.last_modified
                else None,
                "etag": props.etag,
            }

        return await loop.run_in_executor(None, _metadata)
