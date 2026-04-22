"""Dynamic MCP request handlers — no hardcoded connectors."""
import time
from typing import Any, Dict, List

from ..data_sources.base import DocumentConnector, StorageConnector, StructuredConnector
from ..data_sources.registry import ConnectorRegistry
from ..document_processing.embedder import OpenAIEmbedder
from ..document_processing.vector_store import ChromaVectorStore


class MCPHandler:
    """Handles MCP tool requests using the connector registry."""

    def __init__(self, registry: ConnectorRegistry):
        self.registry = registry
        self.vector_store = ChromaVectorStore()
        self.embedder = OpenAIEmbedder()

    async def handle_tool_call(
        self, tool_name: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Route tool calls to appropriate handlers."""
        try:
            start_time = time.time()

            # Dynamic query handlers: query_{source_name}
            if tool_name.startswith("query_"):
                source_name = tool_name[6:]  # strip "query_"
                result = await self._handle_query(source_name, parameters)
            elif tool_name.startswith("list_files_"):
                source_name = tool_name[11:]
                result = await self._handle_list_files(source_name, parameters)
            elif tool_name.startswith("query_documents_"):
                source_name = tool_name[16:]
                result = await self._handle_query_documents(source_name, parameters)
            elif tool_name == "get_schema":
                result = await self._handle_get_schema(parameters)
            elif tool_name == "list_tables":
                result = await self._handle_list_tables(parameters)
            elif tool_name == "get_sample_data":
                result = await self._handle_get_sample_data(parameters)
            elif tool_name == "find_relationships":
                result = await self._handle_find_relationships(parameters)
            elif tool_name == "search_documents":
                result = await self._handle_search_documents(parameters)
            else:
                return {"success": False, "data": None, "error": f"Unknown tool: {tool_name}"}

            execution_time = (time.time() - start_time) * 1000
            return {
                "success": True,
                "data": result,
                "execution_time_ms": execution_time,
            }

        except Exception as e:
            return {"success": False, "data": None, "error": str(e)}

    def _get_structured(self, source_name: str) -> StructuredConnector:
        conn = self.registry.get(source_name)
        if conn is None:
            raise ValueError(f"Unknown source: {source_name}")
        if not isinstance(conn, StructuredConnector):
            raise ValueError(f"Source '{source_name}' is not a structured connector")
        return conn

    async def _handle_query(
        self, source_name: str, params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Execute SQL query against a named source."""
        conn = self._get_structured(source_name)
        query = params.get("query", "")

        # Read-only guard
        upper = query.strip().upper()
        forbidden = ("DROP", "ALTER", "TRUNCATE", "DELETE", "INSERT", "UPDATE", "CREATE")
        if any(upper.startswith(kw) for kw in forbidden):
            raise ValueError("Only SELECT queries are allowed")

        return await conn.execute_query(query)

    async def _handle_list_files(
        self, source_name: str, params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """List files from a storage source."""
        conn = self.registry.get(source_name)
        if not isinstance(conn, StorageConnector):
            raise ValueError(f"Source '{source_name}' is not a storage connector")
        prefix = params.get("prefix", "")
        extensions = params.get("extensions")
        return await conn.list_files(prefix, extensions)

    async def _handle_query_documents(
        self, source_name: str, params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Query documents from a document connector."""
        conn = self.registry.get(source_name)
        if not isinstance(conn, DocumentConnector):
            raise ValueError(f"Source '{source_name}' is not a document connector")
        return await conn.query_documents(
            params["collection"], params["query"], params.get("parameters")
        )

    async def _handle_get_schema(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get table schema from any structured source."""
        conn = self._get_structured(params["source"])
        schema = await conn.get_table_schema(params["table_name"])
        return schema.model_dump()

    async def _handle_list_tables(
        self, params: Dict[str, Any]
    ) -> List[str]:
        """List tables from any structured source."""
        conn = self._get_structured(params["source"])
        return await conn.list_tables()

    async def _handle_get_sample_data(
        self, params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get sample data from any structured source."""
        conn = self._get_structured(params["source"])
        return await conn.get_sample_data(
            params["table_name"], params.get("limit", 5)
        )

    async def _handle_find_relationships(
        self, params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Find relationships between tables across sources."""
        tables = params.get("tables", [])
        relationships = []

        schemas = {}
        for table_info in tables:
            source = table_info["source"]
            table_name = table_info["table_name"]
            conn = self.registry.get(source)
            if conn and isinstance(conn, StructuredConnector):
                schema = await conn.get_table_schema(table_name)
                schemas[f"{source}.{table_name}"] = schema

        for table1_key, schema1 in schemas.items():
            for table2_key, schema2 in schemas.items():
                if table1_key == table2_key:
                    continue

                columns1 = {col["column_name"] for col in schema1.columns}
                columns2 = {col["column_name"] for col in schema2.columns}
                common = columns1 & columns2

                for col in common:
                    if (
                        col in schema1.primary_keys
                        or col in schema2.primary_keys
                        or "_id" in col
                    ):
                        relationships.append(
                            {
                                "table1": table1_key,
                                "table2": table2_key,
                                "column": col,
                                "confidence": "high"
                                if col in schema1.primary_keys or col in schema2.primary_keys
                                else "medium",
                                "type": "potential_foreign_key",
                            }
                        )

                for fk in schema1.foreign_keys:
                    if table2_key.endswith(fk.get("foreign_table_name", "")):
                        relationships.append(
                            {
                                "table1": table1_key,
                                "table2": table2_key,
                                "column": fk.get("column_name"),
                                "foreign_column": fk.get("foreign_column_name"),
                                "confidence": "very_high",
                                "type": "explicit_foreign_key",
                            }
                        )

        return relationships

    async def _handle_search_documents(
        self, params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Search indexed documents via vector store using OpenAI embeddings."""
        query = params["query"]
        n_results = params.get("n_results", 10)

        # Embed the query with the same model used during ingestion (OpenAI)
        # so the vector space matches the stored document embeddings.
        query_embedding = await self.embedder.embed_query(query)
        results = self.vector_store.search(query_embedding, n_results)
        return [
            {"text": r.text, "score": r.score, "metadata": r.metadata}
            for r in results
        ]

    async def cleanup(self):
        """Clean up all connector resources."""
        await self.registry.disconnect_all()
