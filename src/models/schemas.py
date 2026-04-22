"""Pydantic schemas for request/response validation."""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Chat request from user."""

    message: str = Field(..., description="User's question or query")
    session_id: str = Field(..., description="Unique session identifier")
    context: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional context"
    )


class DataSource(BaseModel):
    """Information about a queried structured data source."""

    source: str = Field(..., description="Name of the data source")
    query: str = Field(..., description="SQL query executed")
    records: int = Field(..., description="Number of records returned")
    execution_time_ms: float = Field(
        ..., description="Query execution time in milliseconds"
    )


class DocumentSource(BaseModel):
    """Information about a retrieved document chunk."""

    source: str = Field(..., description="Storage source name")
    file_path: str = Field(..., description="Path to the source file")
    chunk_text: str = Field(..., description="Retrieved text chunk")
    relevance_score: float = Field(
        ..., description="Similarity score (0-1)"
    )


class QueryType(str, Enum):
    """Type of retrieval needed for a query."""

    STRUCTURED_ONLY = "structured_only"
    UNSTRUCTURED_ONLY = "unstructured_only"
    HYBRID = "hybrid"


class ChatResponse(BaseModel):
    """Response from the chatbot."""

    response: str = Field(..., description="Natural language response")
    sources: List[DataSource] = Field(
        default_factory=list, description="Structured data sources used"
    )
    document_sources: List[DocumentSource] = Field(
        default_factory=list, description="Document sources used"
    )
    reasoning: str = Field(
        ..., description="Explanation of the agent's reasoning process"
    )
    query_type: Optional[QueryType] = Field(
        default=None, description="Type of retrieval used"
    )
    session_id: str = Field(..., description="Session identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class QueryPlan(BaseModel):
    """Plan for executing a multi-source query."""

    steps: List[Dict[str, Any]] = Field(
        ..., description="Ordered steps to execute"
    )
    data_sources: List[str] = Field(
        ..., description="Data sources involved"
    )
    relationships: List[Dict[str, str]] = Field(
        default_factory=list, description="Identified relationships"
    )
    estimated_complexity: str = Field(
        ..., description="Query complexity (low, medium, high)"
    )


class TableSchema(BaseModel):
    """Schema information for a database table."""

    source: str = Field(..., description="Data source name")
    table_name: str = Field(..., description="Table name")
    columns: List[Dict[str, Any]] = Field(
        ..., description="Column definitions"
    )
    primary_keys: List[str] = Field(default_factory=list)
    foreign_keys: List[Dict[str, str]] = Field(default_factory=list)


class MCPToolRequest(BaseModel):
    """Request to execute an MCP tool."""

    tool_name: str
    parameters: Dict[str, Any]


class MCPToolResponse(BaseModel):
    """Response from MCP tool execution."""

    success: bool
    data: Any
    error: Optional[str] = None


class IngestionStatus(BaseModel):
    """Status of the document ingestion process."""

    vector_store: Dict[str, Any] = Field(
        default_factory=dict, description="Vector store statistics"
    )
    sources: Dict[str, Any] = Field(
        default_factory=dict, description="Per-source ingestion stats"
    )
