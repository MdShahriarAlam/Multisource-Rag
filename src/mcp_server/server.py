"""Standalone MCP server — optional external entrypoint.

The main FastAPI app (``src.main``) calls :class:`MCPHandler` in-process and
does NOT depend on this server. Run this only when exposing the MCP interface
to external clients (``python -m src.mcp_server.server``).
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import load_sources_config, settings
from ..data_sources.registry import ConnectorRegistry
from ..errors import (
    NotInitialized,
    RAGError,
    rag_error_handler,
    unhandled_exception_handler,
)
from ..logging_config import configure_logging
from ..models.schemas import MCPToolRequest, MCPToolResponse
from .handlers import MCPHandler
from .tools import build_tool_definitions

# Trigger @register decorators
import src.data_sources  # noqa: F401

configure_logging()
log = logging.getLogger(__name__)


class _State:
    handler: Optional[MCPHandler] = None
    tools: list = []


state = _State()


@asynccontextmanager
async def lifespan(app: FastAPI):
    registry = ConnectorRegistry()
    sources = load_sources_config()
    registry.load_from_config(sources)

    results = await registry.connect_all()
    for name, ok in results.items():
        log.info("Source %s: %s", name, "connected" if ok else "degraded")

    state.tools = build_tool_definitions(registry)
    state.handler = MCPHandler(registry)

    yield

    if state.handler is not None:
        await state.handler.cleanup()


app = FastAPI(
    title="Multi-Source MCP Server",
    description="Model Context Protocol server for dynamic multi-source data access",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.add_exception_handler(RAGError, rag_error_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


@app.get("/")
async def root():
    return {
        "name": "Multi-Source MCP Server",
        "version": "2.0.0",
        "protocol": "mcp/1.0",
    }


@app.get("/tools")
async def list_tools():
    return {"tools": state.tools}


@app.post("/tools/execute", response_model=MCPToolResponse)
async def execute_tool(request: MCPToolRequest) -> MCPToolResponse:
    if state.handler is None:
        raise NotInitialized("MCP handler not initialized")
    result = await state.handler.handle_tool_call(request.tool_name, request.parameters)
    return MCPToolResponse(**result)


@app.get("/sources")
async def list_sources():
    if state.handler is None:
        return {"sources": []}
    return {"sources": state.handler.registry.list_sources()}


@app.get("/health")
async def health_check():
    if state.handler is None:
        return {"status": "starting"}
    results = await state.handler.registry.health_check_all()
    degraded = any(not v for v in results.values())
    return {
        "status": "degraded" if degraded else "healthy",
        "sources": results,
    }


def main():
    uvicorn.run(
        "src.mcp_server.server:app",
        host=settings.mcp_server_host,
        port=settings.mcp_server_port,
        reload=(settings.env != "prod"),
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
