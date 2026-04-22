"""Ingestion pipeline: storage sources -> parse -> chunk -> embed -> vector store."""
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..data_sources.base import StorageConnector
from ..data_sources.registry import ConnectorRegistry
from .chunker import DocumentChunk, TextChunker
from .embedder import OpenAIEmbedder
from .parsers import ParserFactory
from .vector_store import ChromaVectorStore


class IngestionPipeline:
    """Orchestrates document ingestion from storage sources into ChromaDB."""

    STATE_FILE = ".ingestion_state.json"

    def __init__(
        self,
        registry: ConnectorRegistry,
        vector_store: Optional[ChromaVectorStore] = None,
        embedder: Optional[OpenAIEmbedder] = None,
        chunker: Optional[TextChunker] = None,
    ):
        self.registry = registry
        self.vector_store = vector_store or ChromaVectorStore()
        self.embedder = embedder or OpenAIEmbedder()
        self.chunker = chunker or TextChunker()
        self._state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """Load ingestion state (tracks processed files)."""
        path = Path(self.STATE_FILE)
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
        return {"sources": {}}

    def _save_state(self) -> None:
        """Persist ingestion state."""
        with open(self.STATE_FILE, "w") as f:
            json.dump(self._state, f, indent=2)

    async def ingest_all(self) -> Dict[str, Any]:
        """Ingest documents from all enabled storage sources."""
        storage_connectors = self.registry.get_storage()
        results = {}

        for name, connector in storage_connectors.items():
            result = await self.ingest_source(name)
            results[name] = result

        return results

    async def ingest_source(self, source_name: str) -> Dict[str, Any]:
        """Ingest documents from a single storage source."""
        connector = self.registry.get(source_name)
        if connector is None:
            return {"error": f"Source '{source_name}' not found"}

        if not isinstance(connector, StorageConnector):
            return {"error": f"Source '{source_name}' is not a storage connector"}

        start_time = time.time()
        stats = {
            "source": source_name,
            "files_processed": 0,
            "files_skipped": 0,
            "chunks_created": 0,
            "errors": [],
        }

        try:
            files = await connector.list_files()
        except Exception as e:
            return {"error": f"Failed to list files: {e}"}

        source_state = self._state.get("sources", {}).get(source_name, {})

        for file_info in files:
            file_name = file_info["name"]
            last_modified = file_info.get("last_modified", "")

            # Skip if already processed and unchanged
            prev = source_state.get(file_name)
            if prev and prev.get("last_modified") == last_modified:
                stats["files_skipped"] += 1
                continue

            try:
                content = await connector.download_file(file_name)
                parser = ParserFactory.get_parser(file_name)
                segments = parser.parse(content, file_name)

                base_metadata = {
                    "source_name": source_name,
                    "file_path": file_name,
                    "source_type": connector.source_type,
                }

                chunks = self.chunker.chunk_segments(segments, base_metadata)

                if chunks:
                    embeddings = await self.embedder.embed_chunks(chunks)
                    self.vector_store.add_documents(chunks, embeddings)

                stats["files_processed"] += 1
                stats["chunks_created"] += len(chunks)

                # Update state
                if source_name not in self._state["sources"]:
                    self._state["sources"][source_name] = {}
                self._state["sources"][source_name][file_name] = {
                    "last_modified": last_modified,
                    "chunks": len(chunks),
                    "ingested_at": time.time(),
                }

            except Exception as e:
                stats["errors"].append({"file": file_name, "error": str(e)})

        self._save_state()
        stats["duration_seconds"] = round(time.time() - start_time, 2)
        return stats

    def get_status(self) -> Dict[str, Any]:
        """Get ingestion status summary."""
        vector_stats = self.vector_store.get_stats()
        source_stats = {}

        for source_name, files in self._state.get("sources", {}).items():
            source_stats[source_name] = {
                "files_ingested": len(files),
                "total_chunks": sum(f.get("chunks", 0) for f in files.values()),
            }

        return {
            "vector_store": vector_stats,
            "sources": source_stats,
        }
