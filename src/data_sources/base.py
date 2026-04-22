"""Base connector interfaces for data sources."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..models.schemas import TableSchema


class BaseConnector(ABC):
    """Abstract base for all data source connectors."""

    source_type: str = ""

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the data source."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the data source."""

    async def test_connection(self) -> bool:
        """Test if connection is working."""
        try:
            await self.connect()
            await self.disconnect()
            return True
        except Exception:
            return False


class StructuredConnector(BaseConnector):
    """Base for SQL/queryable database connectors (Postgres, BigQuery, Azure SQL)."""

    @abstractmethod
    async def execute_query(
        self, query: str, params: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """Execute a SQL query with optional parameterized values."""

    @abstractmethod
    async def get_table_schema(self, table_name: str) -> TableSchema:
        """Get schema information for a table."""

    @abstractmethod
    async def list_tables(self) -> List[str]:
        """List all available tables."""

    @abstractmethod
    async def get_sample_data(
        self, table_name: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get sample data from a table (must validate table_name)."""

    async def validate_table_name(self, table_name: str) -> bool:
        """Check that a table name exists (prevent injection)."""
        tables = await self.list_tables()
        return table_name in tables


class StorageConnector(BaseConnector):
    """Base for blob/object storage connectors (Azure Blob, GCS, S3)."""

    @abstractmethod
    async def list_files(
        self,
        prefix: str = "",
        extensions: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """List files, optionally filtered by prefix and extensions.

        Returns list of dicts with at least: name, size, last_modified.
        """

    @abstractmethod
    async def download_file(self, file_path: str) -> bytes:
        """Download a file and return its contents as bytes."""

    @abstractmethod
    async def get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """Get metadata for a file (content_type, size, last_modified, etc.)."""


class DocumentConnector(BaseConnector):
    """Base for semi-structured / NoSQL connectors (Cosmos DB, MongoDB)."""

    @abstractmethod
    async def list_collections(self) -> List[str]:
        """List available collections/containers."""

    @abstractmethod
    async def query_documents(
        self,
        collection: str,
        query: str,
        parameters: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Query documents in a collection."""

    @abstractmethod
    async def get_document(
        self, collection: str, doc_id: str, partition_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get a single document by ID."""
