"""MCP Server module.

Import the FastAPI app lazily via ``from src.mcp_server.server import app`` —
eagerly loading it here would pull chromadb during unrelated test collection.
"""
from .handlers import MCPHandler
from .tools import build_tool_definitions

__all__ = ["MCPHandler", "build_tool_definitions"]
