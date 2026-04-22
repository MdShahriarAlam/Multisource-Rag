"""Pydantic schemas for request/response validation."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..config import settings


class ChatRequest(BaseModel):
    """Chat request from user."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=settings.max_message_chars,
        description="User's question or query",
    )
    session_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_\-]+$",
        description="Unique session identifier (alphanumeric / dash / underscore)",
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional context (e.g. uploaded_file)"
    )


class DataSource(BaseModel):
    """Information about a queried structured data source."""

    source: str
    query: str
    records: int
    execution_time_ms: float


class DocumentSource(BaseModel):
    """Information about a retrieved document chunk."""

    source: str
    file_path: str
    chunk_text: str
    relevance_score: float


class QueryType(str, Enum):
    """Type of retrieval needed for a query."""

    STRUCTURED_ONLY = "structured_only"
    UNSTRUCTURED_ONLY = "unstructured_only"
    HYBRID = "hybrid"


class ChatResponse(BaseModel):
    """Response from the chatbot."""

    response: str
    sources: List[DataSource] = Field(default_factory=list)
    document_sources: List[DocumentSource] = Field(default_factory=list)
    reasoning: str
    query_type: Optional[QueryType] = None
    session_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TableSchema(BaseModel):
    """Schema information for a database table."""

    source: str
    table_name: str
    columns: List[Dict[str, Any]]
    primary_keys: List[str] = Field(default_factory=list)
    foreign_keys: List[Dict[str, str]] = Field(default_factory=list)


class MCPToolRequest(BaseModel):
    """Request to execute an MCP tool."""

    tool_name: str = Field(..., min_length=1, max_length=128)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class MCPToolResponse(BaseModel):
    """Response from MCP tool execution."""

    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None


class IngestionStatus(BaseModel):
    """Status of the document ingestion process."""

    vector_store: Dict[str, Any] = Field(default_factory=dict)
    sources: Dict[str, Any] = Field(default_factory=dict)


class SourceStatus(BaseModel):
    """Per-source health information."""

    name: str
    type: str
    connector_class: str
    connected: bool
    healthy: Optional[bool] = None
    error: Optional[str] = None
