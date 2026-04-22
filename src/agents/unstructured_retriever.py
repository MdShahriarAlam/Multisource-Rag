"""Unstructured retriever — handles vector-based document retrieval."""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..config import settings
from ..document_processing.embedder import OpenAIEmbedder
from ..document_processing.vector_store import ChromaVectorStore, SearchResult
from ..models.schemas import DocumentSource

log = logging.getLogger(__name__)


@dataclass
class UnstructuredResult:
    """Result from unstructured (vector) retrieval."""

    chunks: List[SearchResult] = field(default_factory=list)
    document_sources: List[DocumentSource] = field(default_factory=list)
    reasoning_steps: List[str] = field(default_factory=list)


class UnstructuredRetriever:
    """Retrieves relevant document chunks from the vector store."""

    def __init__(
        self,
        vector_store: Optional[ChromaVectorStore] = None,
        embedder: Optional[OpenAIEmbedder] = None,
    ):
        self.vector_store = vector_store or ChromaVectorStore()
        self.embedder = embedder or OpenAIEmbedder()

    async def retrieve(
        self,
        user_query: str,
        analysis: Dict[str, Any],
        n_results: int = 10,
    ) -> UnstructuredResult:
        """Search the vector store for relevant document chunks."""
        result = UnstructuredResult()

        stats = self.vector_store.get_stats()
        if stats["total_chunks"] == 0:
            result.reasoning_steps.append("No documents indexed yet")
            return result

        result.reasoning_steps.append(
            f"Searching {stats['total_chunks']} document chunks..."
        )

        # Embed the query and search
        try:
            query_embedding = await self.embedder.embed_query(user_query)
            search_results = self.vector_store.search(
                query_embedding=query_embedding,
                n_results=n_results,
            )
        except Exception as e:
            log.exception("Vector search failed")
            result.reasoning_steps.append(f"Vector search error: {e}")
            return result

        if not search_results:
            result.reasoning_steps.append("No relevant documents found")
            return result

        threshold = settings.unstructured_relevance_threshold
        relevant = [r for r in search_results if r.score >= threshold]
        result.chunks = relevant

        # Dedupe by (source, file_path) — keep highest-scoring chunk per file
        best: Dict[Tuple[str, str], DocumentSource] = {}
        for chunk in relevant:
            source_name = chunk.metadata.get("source_name", "unknown")
            file_path = chunk.metadata.get("file_path", "unknown")
            key = (source_name, file_path)
            snippet = chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text
            candidate = DocumentSource(
                source=source_name,
                file_path=file_path,
                chunk_text=snippet,
                relevance_score=chunk.score,
            )
            if key not in best or candidate.relevance_score > best[key].relevance_score:
                best[key] = candidate

        result.document_sources = list(best.values())
        result.reasoning_steps.append(
            f"Found {len(relevant)} relevant chunks from {len(best)} file(s)"
        )
        return result

    def has_documents(self) -> bool:
        """Check if any documents have been indexed."""
        return self.vector_store.get_stats()["total_chunks"] > 0
