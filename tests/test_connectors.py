"""Tests for data source connectors."""
import pytest
from tests.conftest import MockStructuredConnector, MockStorageConnector


class TestMockStructuredConnector:
    @pytest.mark.asyncio
    async def test_list_tables(self):
        conn = MockStructuredConnector()
        tables = await conn.list_tables()
        assert "customers" in tables
        assert "orders" in tables

    @pytest.mark.asyncio
    async def test_execute_query(self):
        conn = MockStructuredConnector()
        result = await conn.execute_query("SELECT * FROM customers")
        assert len(result) == 2
        assert result[0]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_get_table_schema(self):
        conn = MockStructuredConnector()
        schema = await conn.get_table_schema("customers")
        assert schema.table_name == "customers"
        assert schema.source == "mock_db"
        col_names = [c["column_name"] for c in schema.columns]
        assert "name" in col_names

    @pytest.mark.asyncio
    async def test_get_table_schema_invalid(self):
        conn = MockStructuredConnector()
        with pytest.raises(ValueError, match="does not exist"):
            await conn.get_table_schema("nonexistent")

    @pytest.mark.asyncio
    async def test_validate_table_name(self):
        conn = MockStructuredConnector()
        assert await conn.validate_table_name("customers") is True
        assert await conn.validate_table_name("nonexistent") is False

    @pytest.mark.asyncio
    async def test_get_sample_data(self):
        conn = MockStructuredConnector()
        data = await conn.get_sample_data("orders", limit=1)
        assert len(data) == 1


class TestMockStorageConnector:
    @pytest.mark.asyncio
    async def test_list_files(self):
        conn = MockStorageConnector()
        files = await conn.list_files()
        names = [f["name"] for f in files]
        assert "report.txt" in names
        assert "data.csv" in names

    @pytest.mark.asyncio
    async def test_list_files_with_extension_filter(self):
        conn = MockStorageConnector()
        files = await conn.list_files(extensions=[".txt"])
        names = [f["name"] for f in files]
        assert "report.txt" in names
        assert "data.csv" not in names

    @pytest.mark.asyncio
    async def test_download_file(self):
        conn = MockStorageConnector()
        content = await conn.download_file("report.txt")
        assert b"quarterly report" in content

    @pytest.mark.asyncio
    async def test_download_file_not_found(self):
        conn = MockStorageConnector()
        with pytest.raises(FileNotFoundError):
            await conn.download_file("nonexistent.txt")
