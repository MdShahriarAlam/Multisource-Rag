"""Shared test fixtures."""
import os
import tempfile
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock

import pytest

# Set minimal env vars before importing app modules
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("OPENAI_MODEL", "gpt-4-turbo-preview")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", "fake.json")
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("BIGQUERY_DATASET", "test_dataset")

from src.data_sources.base import StorageConnector, StructuredConnector
from src.data_sources.registry import ConnectorRegistry, register
from src.models.schemas import TableSchema


class MockStructuredConnector(StructuredConnector):
    """Mock structured connector for testing."""

    source_type = "mock_sql"

    def __init__(self, name: str = "mock_db", config: Dict[str, Any] = None):
        super().__init__(name, config or {})
        self._tables = {
            "customers": [
                {"id": 1, "name": "Alice", "email": "alice@example.com"},
                {"id": 2, "name": "Bob", "email": "bob@example.com"},
            ],
            "orders": [
                {"id": 1, "customer_id": 1, "amount": 100.0},
                {"id": 2, "customer_id": 2, "amount": 200.0},
            ],
        }

    async def connect(self):
        pass

    async def disconnect(self):
        pass

    async def execute_query(self, query: str, params: Optional[tuple] = None):
        # Return mock data based on table name in query
        for table in self._tables:
            if table in query.lower():
                return self._tables[table]
        return []

    async def get_table_schema(self, table_name: str) -> TableSchema:
        if table_name not in self._tables:
            raise ValueError(f"Table '{table_name}' does not exist")
        sample = self._tables[table_name][0]
        columns = [
            {"column_name": k, "data_type": "varchar"} for k in sample.keys()
        ]
        return TableSchema(
            source=self.name,
            table_name=table_name,
            columns=columns,
            primary_keys=["id"],
            foreign_keys=[],
        )

    async def list_tables(self) -> List[str]:
        return list(self._tables.keys())

    async def get_sample_data(self, table_name: str, limit: int = 5):
        if table_name not in self._tables:
            raise ValueError(f"Table '{table_name}' does not exist")
        return self._tables[table_name][:limit]


class MockStorageConnector(StorageConnector):
    """Mock storage connector for testing."""

    source_type = "mock_storage"

    def __init__(self, name: str = "mock_store", config: Dict[str, Any] = None):
        super().__init__(name, config or {})
        self._files = {
            "report.txt": b"This is a quarterly report about margins and revenue.",
            "data.csv": b"name,value\nAlice,100\nBob,200\n",
        }

    async def connect(self):
        pass

    async def disconnect(self):
        pass

    async def list_files(self, prefix="", extensions=None):
        files = []
        for name, content in self._files.items():
            ext = "." + name.rsplit(".", 1)[-1]
            if extensions and ext not in extensions:
                continue
            files.append(
                {"name": name, "size": len(content), "last_modified": "2024-01-01T00:00:00"}
            )
        return files

    async def download_file(self, file_path: str) -> bytes:
        if file_path not in self._files:
            raise FileNotFoundError(file_path)
        return self._files[file_path]

    async def get_file_metadata(self, file_path: str):
        if file_path not in self._files:
            raise FileNotFoundError(file_path)
        return {"name": file_path, "size": len(self._files[file_path])}


@pytest.fixture
def mock_registry():
    """Registry with mock connectors."""
    reg = ConnectorRegistry()
    reg._connectors["mock_db"] = MockStructuredConnector()
    reg._connectors["mock_store"] = MockStorageConnector()
    return reg


@pytest.fixture
def temp_chroma_dir():
    """Temporary directory for ChromaDB."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    # ChromaDB holds file locks on Windows; ignore cleanup errors
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)
