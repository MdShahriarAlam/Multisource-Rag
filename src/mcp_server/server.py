"""MCP Server implementation with dynamic connector registry."""
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ..config import load_sources_config, settings
from ..data_sources.registry import ConnectorRegistry
from ..models.schemas import MCPToolRequest, MCPToolResponse
from .handlers import MCPHandler
from .tools import build_tool_definitions

# Import connectors to trigger @register decorators
import src.data_sources  # noqa: F401

# Global state
mcp_handler: MCPHandler = None
mcp_tools = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global mcp_handler, mcp_tools

    # Build registry from config
    registry = ConnectorRegistry()
    sources = load_sources_config()
    registry.load_from_config(sources)

    # Connect all sources
    results = await registry.connect_all()
    for name, success in results.items():
        status = "connected" if success else "FAILED"
        print(f"  [{status}] {name}")

    # Build tools and handler
    mcp_tools = build_tool_definitions(registry)
    mcp_handler = MCPHandler(registry)

    yield

    await mcp_handler.cleanup()


app = FastAPI(
    title="Multi-Source MCP Server",
    description="Model Context Protocol server for dynamic multi-source data access",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "name": "Multi-Source MCP Server",
        "version": "2.0.0",
        "protocol": "mcp/1.0",
    }


@app.get("/tools")
async def list_tools():
    return {"tools": mcp_tools}


@app.post("/tools/execute", response_model=MCPToolResponse)
async def execute_tool(request: MCPToolRequest):
    global mcp_handler
    if not mcp_handler:
        raise HTTPException(status_code=500, detail="MCP handler not initialized")
    result = await mcp_handler.handle_tool_call(request.tool_name, request.parameters)
    return MCPToolResponse(**result)


@app.get("/sources")
async def list_sources():
    """List all connected data sources."""
    global mcp_handler
    if not mcp_handler:
        return {"sources": []}
    return {"sources": mcp_handler.registry.list_sources()}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


def main():
    uvicorn.run(
        "src.mcp_server.server:app",
        host=settings.mcp_server_host,
        port=settings.mcp_server_port,
        reload=True,
    )


if __name__ == "__main__":
    main()
