"""Dynamic MCP request handlers — typed errors, parse-tree SQL safety."""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from ..config import settings
from ..data_sources.base import DocumentConnector, StorageConnector, StructuredConnector
from ..data_sources.registry import ConnectorRegistry
from ..document_processing.embedder import OpenAIEmbedder
from ..document_processing.vector_store import ChromaVectorStore
from ..errors import InvalidInput, RAGError, SourceNotFound
from .sql_safety import ensure_select_only

log = logging.getLogger(__name__)


class MCPHandler:
    """Handles MCP tool requests using the connector registry."""

    SEARCH_QUERY_MAX_CHARS = 1000

    def __init__(
        self,
        registry: ConnectorRegistry,
        vector_store: Optional[ChromaVectorStore] = None,
        embedder: Optional[OpenAIEmbedder] = None,
    ):
        self.registry = registry
        self._vector_store: Optional[ChromaVectorStore] = vector_store
        self._embedder: Optional[OpenAIEmbedder] = embedder

    @property
    def vector_store(self) -> ChromaVectorStore:
        if self._vector_store is None:
            self._vector_store = ChromaVectorStore()
        return self._vector_store

    @property
    def embedder(self) -> OpenAIEmbedder:
        if self._embedder is None:
            self._embedder = OpenAIEmbedder()
        return self._embedder

    async def handle_tool_call(
        self, tool_name: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Route tool calls. Returns uniform {success, data, error, execution_time_ms}."""
        start = time.time()
        try:
            data = await self._dispatch(tool_name, parameters)
            return {
                "success": True,
                "data": data,
                "error": None,
                "execution_time_ms": (time.time() - start) * 1000,
            }
        except RAGError as e:
            log.warning("Tool %s rejected: %s", tool_name, e.message)
            return {
                "success": False,
                "data": None,
                "error": f"{e.error_code}: {e.message}",
                "execution_time_ms": (time.time() - start) * 1000,
            }
        except Exception as e:
            # Unexpected — log with stack, return sanitized string to caller.
            log.exception("Tool %s failed", tool_name)
            return {
                "success": False,
                "data": None,
                "error": f"{type(e).__name__}: {e}",
                "execution_time_ms": (time.time() - start) * 1000,
            }

    async def _dispatch(self, tool_name: str, params: Dict[str, Any]) -> Any:
        if tool_name.startswith("query_documents_"):
            return await self._handle_query_documents(tool_name[len("query_documents_"):], params)
        if tool_name.startswith("query_"):
            return await self._handle_query(tool_name[len("query_"):], params)
        if tool_name.startswith("list_files_"):
            return await self._handle_list_files(tool_name[len("list_files_"):], params)
        if tool_name == "get_schema":
            return await self._handle_get_schema(params)
        if tool_name == "list_tables":
            return await self._handle_list_tables(params)
        if tool_name == "get_sample_data":
            return await self._handle_get_sample_data(params)
        if tool_name == "find_relationships":
            return await self._handle_find_relationships(params)
        if tool_name == "search_documents":
            return await self._handle_search_documents(params)
        raise InvalidInput(f"Unknown tool: {tool_name}")

    # ── Resolution helpers ──────────────────────────────────────────────────

    def _get_structured(self, source_name: str) -> StructuredConnector:
        conn = self.registry.get(source_name)
        if conn is None:
            raise SourceNotFound(f"Unknown source: {source_name}")
        if not isinstance(conn, StructuredConnector):
            raise InvalidInput(f"Source '{source_name}' is not a structured connector")
        return conn

    def _get_storage(self, source_name: str) -> StorageConnector:
        conn = self.registry.get(source_name)
        if conn is None:
            raise SourceNotFound(f"Unknown source: {source_name}")
        if not isinstance(conn, StorageConnector):
            raise InvalidInput(f"Source '{source_name}' is not a storage connector")
        return conn

    def _get_document(self, source_name: str) -> DocumentConnector:
        conn = self.registry.get(source_name)
        if conn is None:
            raise SourceNotFound(f"Unknown source: {source_name}")
        if not isinstance(conn, DocumentConnector):
            raise InvalidInput(f"Source '{source_name}' is not a document connector")
        return conn

    @staticmethod
    def _require(params: Dict[str, Any], key: str) -> Any:
        if key not in params or params[key] in (None, ""):
            raise InvalidInput(f"Missing required parameter: '{key}'")
        return params[key]

    # ── Tool handlers ───────────────────────────────────────────────────────

    async def _handle_query(self, source_name: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        conn = self._get_structured(source_name)
        raw = self._require(params, "query")
        if not isinstance(raw, str):
            raise InvalidInput("'query' must be a string")
        safe_query = ensure_select_only(raw)
        return await conn.execute_query(safe_query)

    async def _handle_list_files(self, source_name: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        conn = self._get_storage(source_name)
        prefix = params.get("prefix", "") or ""
        extensions = params.get("extensions")
        if extensions is not None and not isinstance(extensions, list):
            raise InvalidInput("'extensions' must be a list of strings if provided")
        return await conn.list_files(prefix, extensions)

    async def _handle_query_documents(
        self, source_name: str, params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        conn = self._get_document(source_name)
        collection = self._require(params, "collection")
        query = self._require(params, "query")
        return await conn.query_documents(collection, query, params.get("parameters"))

    async def _handle_get_schema(self, params: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._get_structured(self._require(params, "source"))
        schema = await conn.get_table_schema(self._require(params, "table_name"))
        return schema.model_dump()

    async def _handle_list_tables(self, params: Dict[str, Any]) -> List[str]:
        conn = self._get_structured(self._require(params, "source"))
        return await conn.list_tables()

    async def _handle_get_sample_data(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        conn = self._get_structured(self._require(params, "source"))
        table_name = self._require(params, "table_name")
        try:
            limit = int(params.get("limit", 5))
        except (TypeError, ValueError) as e:
            raise InvalidInput("'limit' must be an integer") from e
        limit = max(1, min(limit, 100))
        return await conn.get_sample_data(table_name, limit)

    async def _handle_find_relationships(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        tables = params.get("tables", [])
        if not isinstance(tables, list):
            raise InvalidInput("'tables' must be a list of {source, table_name} objects")

        schemas = {}
        for table_info in tables:
            if not isinstance(table_info, dict):
                raise InvalidInput("Each table entry must be an object with 'source' and 'table_name'")
            source = self._require(table_info, "source")
            table_name = self._require(table_info, "table_name")
            conn = self.registry.get(source)
            if conn and isinstance(conn, StructuredConnector):
                schemas[f"{source}.{table_name}"] = await conn.get_table_schema(table_name)

        relationships: List[Dict[str, Any]] = []
        items = list(schemas.items())
        for i, (key1, schema1) in enumerate(items):
            for key2, schema2 in items[i + 1:]:
                cols1 = {col["column_name"]: col for col in schema1.columns}
                cols2 = {col["column_name"]: col for col in schema2.columns}
                for col_name in cols1.keys() & cols2.keys():
                    if (
                        col_name in schema1.primary_keys
                        or col_name in schema2.primary_keys
                        or "_id" in col_name
                    ):
                        relationships.append({
                            "table1": key1,
                            "table2": key2,
                            "column": col_name,
                            "confidence": "high" if (
                                col_name in schema1.primary_keys
                                or col_name in schema2.primary_keys
                            ) else "medium",
                            "type": "potential_foreign_key",
                        })
                for fk in schema1.foreign_keys:
                    if key2.endswith(fk.get("foreign_table_name", "")):
                        relationships.append({
                            "table1": key1,
                            "table2": key2,
                            "column": fk.get("column_name"),
                            "foreign_column": fk.get("foreign_column_name"),
                            "confidence": "very_high",
                            "type": "explicit_foreign_key",
                        })
        return relationships

    async def _handle_search_documents(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        raw_query = self._require(params, "query")
        if not isinstance(raw_query, str):
            raise InvalidInput("'query' must be a string")
        # Bound the embedding input — protects against DoS / giant token bills.
        query = raw_query[: self.SEARCH_QUERY_MAX_CHARS]
        try:
            n_results = int(params.get("n_results", 10))
        except (TypeError, ValueError) as e:
            raise InvalidInput("'n_results' must be an integer") from e
        n_results = max(1, min(n_results, 50))

        query_embedding = await self.embedder.embed_query(query)
        results = self.vector_store.search(query_embedding, n_results)
        threshold = settings.unstructured_relevance_threshold
        return [
            {"text": r.text, "score": r.score, "metadata": r.metadata}
            for r in results
            if r.score >= threshold
        ]

    async def cleanup(self) -> None:
        """Close all connector resources. Never raises."""
        await self.registry.disconnect_all()
