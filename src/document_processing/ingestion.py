"""Ingestion pipeline: storage sources -> parse -> chunk -> embed -> vector store."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from ..config import settings
from ..data_sources.base import StorageConnector
from ..data_sources.registry import ConnectorRegistry
from ..errors import IngestionError, SourceNotFound
from .chunker import TextChunker
from .embedder import OpenAIEmbedder
from .parsers import ParserFactory
from .vector_store import ChromaVectorStore

log = logging.getLogger(__name__)


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
        self._lock = asyncio.Lock()

    # ── State persistence (atomic) ──────────────────────────────────────────

    def _load_state(self) -> Dict[str, Any]:
        path = Path(self.STATE_FILE)
        if not path.exists():
            return {"sources": {}}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict) or "sources" not in data:
                    return {"sources": {}}
                return data
        except (json.JSONDecodeError, OSError):
            log.exception("Corrupt ingestion state — resetting")
            return {"sources": {}}

    def _save_state(self) -> None:
        """Write atomically: tmp file + os.replace()."""
        path = Path(self.STATE_FILE)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    # ── Public API ──────────────────────────────────────────────────────────

    async def ingest_all(self) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        for name in self.registry.get_storage().keys():
            results[name] = await self.ingest_source(name)
        return results

    async def ingest_source(self, source_name: str) -> Dict[str, Any]:
        """Ingest from a single storage source. Serialized per-pipeline via lock."""
        async with self._lock:
            return await self._ingest_source_locked(source_name)

    async def _ingest_source_locked(self, source_name: str) -> Dict[str, Any]:
        connector = self.registry.get(source_name)
        if connector is None:
            raise SourceNotFound(f"Source '{source_name}' not found")
        if not isinstance(connector, StorageConnector):
            raise IngestionError(
                f"Source '{source_name}' is not a storage connector",
                details={"source_type": getattr(connector, "source_type", None)},
            )

        start_time = time.time()
        stats: Dict[str, Any] = {
            "source": source_name,
            "files_processed": 0,
            "files_skipped": 0,
            "chunks_created": 0,
            "errors": [],
        }

        try:
            files = await connector.list_files()
        except Exception as e:
            log.exception("Failed to list files for source %s", source_name)
            raise IngestionError(
                f"Failed to list files for '{source_name}'",
                details={"error": str(e)},
            ) from e

        source_state = self._state.get("sources", {}).get(source_name, {})

        for file_info in files:
            file_name = file_info["name"]
            last_modified = file_info.get("last_modified", "")
            size = file_info.get("size", 0)

            if size and size > settings.max_file_bytes:
                stats["errors"].append(
                    {"file": file_name, "error": f"exceeds max_file_bytes ({size})"}
                )
                continue

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

                self._state.setdefault("sources", {}).setdefault(source_name, {})[file_name] = {
                    "last_modified": last_modified,
                    "chunks": len(chunks),
                    "ingested_at": time.time(),
                }

            except Exception as e:
                log.exception("Failed to ingest %s/%s", source_name, file_name)
                stats["errors"].append({"file": file_name, "error": str(e)})

        self._save_state()
        stats["duration_seconds"] = round(time.time() - start_time, 2)
        return stats

    def get_status(self) -> Dict[str, Any]:
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
