"""MCPHandler dispatch + error envelope tests."""
import pytest

from src.mcp_server.handlers import MCPHandler


@pytest.fixture
def handler(mock_registry):
    return MCPHandler(mock_registry)


@pytest.mark.asyncio
async def test_list_tables_success(handler):
    result = await handler.handle_tool_call("list_tables", {"source": "mock_db"})
    assert result["success"] is True
    assert "customers" in result["data"]


@pytest.mark.asyncio
async def test_query_rejects_dml(handler):
    result = await handler.handle_tool_call(
        "query_mock_db", {"query": "DELETE FROM customers"}
    )
    assert result["success"] is False
    assert "unsafe_query" in result["error"]


@pytest.mark.asyncio
async def test_query_allows_select(handler):
    result = await handler.handle_tool_call(
        "query_mock_db", {"query": "SELECT * FROM customers"}
    )
    assert result["success"] is True
    assert len(result["data"]) == 2


@pytest.mark.asyncio
async def test_unknown_tool(handler):
    result = await handler.handle_tool_call("nope", {})
    assert result["success"] is False
    assert "invalid_input" in result["error"]


@pytest.mark.asyncio
async def test_missing_required_param(handler):
    result = await handler.handle_tool_call("list_tables", {})
    assert result["success"] is False
    assert "invalid_input" in result["error"]


@pytest.mark.asyncio
async def test_unknown_source(handler):
    result = await handler.handle_tool_call("list_tables", {"source": "nonexistent"})
    assert result["success"] is False
    assert "source_not_found" in result["error"]
