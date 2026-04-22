"""Dynamic MCP tool definitions based on registered data sources."""
from typing import Any, Dict, List

from ..data_sources.base import DocumentConnector, StorageConnector, StructuredConnector
from ..data_sources.registry import ConnectorRegistry


def build_tool_definitions(registry: ConnectorRegistry) -> List[Dict[str, Any]]:
    """Generate tool definitions dynamically from enabled connectors."""
    tools = []
    source_names = []

    # Structured connectors -> query, list_tables, get_schema, get_sample_data
    for name, conn in registry.get_structured().items():
        source_names.append(name)
        tools.append(
            {
                "name": f"query_{name}",
                "description": f"Execute a SQL query against {name} ({conn.source_type})",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "SQL query to execute"}
                    },
                    "required": ["query"],
                },
            }
        )

    # Storage connectors -> list_files, download_file
    for name, conn in registry.get_storage().items():
        source_names.append(name)
        tools.append(
            {
                "name": f"list_files_{name}",
                "description": (
                    f"List file names stored in {name} ({conn.source_type}). "
                    f"Returns filenames and sizes ONLY — it does NOT return file content. "
                    f"To read the actual content of a document, use search_documents instead."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "prefix": {"type": "string", "description": "Path prefix filter", "default": ""},
                        "extensions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "File extensions to filter",
                        },
                    },
                },
            }
        )

    # Document connectors -> query_documents, list_collections
    for name, conn in registry.get_document().items():
        source_names.append(name)
        tools.append(
            {
                "name": f"query_documents_{name}",
                "description": f"Query documents in {name} ({conn.source_type})",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "collection": {"type": "string", "description": "Collection/container name"},
                        "query": {"type": "string", "description": "Query string"},
                    },
                    "required": ["collection", "query"],
                },
            }
        )

    # Generic tools (work across all structured sources)
    if source_names:
        tools.extend(
            [
                {
                    "name": "get_schema",
                    "description": "Get schema information for a table from a specific data source",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "source": {"type": "string", "description": "Data source name"},
                            "table_name": {"type": "string", "description": "Name of the table"},
                        },
                        "required": ["source", "table_name"],
                    },
                },
                {
                    "name": "list_tables",
                    "description": "List all available tables from a data source",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "source": {"type": "string", "description": "Data source name"},
                        },
                        "required": ["source"],
                    },
                },
                {
                    "name": "get_sample_data",
                    "description": "Get sample data from a table",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "source": {"type": "string", "description": "Data source name"},
                            "table_name": {"type": "string", "description": "Name of the table"},
                            "limit": {"type": "integer", "description": "Number of rows", "default": 5},
                        },
                        "required": ["source", "table_name"],
                    },
                },
                {
                    "name": "find_relationships",
                    "description": "Discover relationships between tables across data sources",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "tables": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "source": {"type": "string"},
                                        "table_name": {"type": "string"},
                                    },
                                },
                                "description": "List of tables to analyze",
                            }
                        },
                        "required": ["tables"],
                    },
                },
                {
                    "name": "search_documents",
                    "description": (
                        "Read and search the content of uploaded PDFs and indexed documents. "
                        "This is the ONLY tool that returns actual document text. "
                        "Use it to: extract invoice details, read order information, find customer data in a PDF, "
                        "or answer any question about document content. "
                        "Pass descriptive terms about what you are looking for (e.g. 'invoice customer order details', "
                        "'product names prices', 'Alice Johnson order'). "
                        "Call this FIRST whenever the user mentions or attaches a document."
                    ),
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search terms describing the content you want to extract"},
                            "n_results": {"type": "integer", "description": "Number of result chunks to return (default 10)", "default": 10},
                        },
                        "required": ["query"],
                    },
                },
            ]
        )

    return tools
