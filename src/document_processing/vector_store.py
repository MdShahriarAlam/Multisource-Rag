"""ChromaDB vector store for document embeddings."""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import chromadb

from ..config import settings
from .chunker import DocumentChunk


@dataclass
class SearchResult:
    """A single search result from the vector store."""

    text: str
    score: float
    metadata: Dict[str, Any]


class ChromaVectorStore:
    """Persistent ChromaDB vector store for document chunks."""

    COLLECTION_NAME = "multisource_rag"

    def __init__(self, persist_dir: str = None):
        self.persist_dir = persist_dir or settings.chroma_persist_dir
        self.client = chromadb.PersistentClient(path=self.persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(
        self,
        chunks: List[DocumentChunk],
        embeddings: List[List[float]],
    ) -> int:
        """Add document chunks with their embeddings. Returns count added."""
        if not chunks:
            return 0

        ids = [c.id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [
            {k: str(v) for k, v in c.metadata.items()} for c in chunks
        ]

        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        return len(chunks)

    def search(
        self,
        query_embedding: List[float],
        n_results: int = 10,
        filter_dict: Optional[Dict[str, str]] = None,
    ) -> List[SearchResult]:
        """Search for similar documents by embedding vector."""
        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": min(n_results, self.collection.count() or 1),
        }
        if filter_dict:
            kwargs["where"] = filter_dict

        results = self.collection.query(**kwargs)

        search_results = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                score = 1.0 - (results["distances"][0][i] if results["distances"] else 0)
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                search_results.append(
                    SearchResult(text=doc, score=score, metadata=metadata)
                )

        return search_results

    def search_by_text(
        self,
        query: str,
        n_results: int = 10,
        filter_dict: Optional[Dict[str, str]] = None,
    ) -> List[SearchResult]:
        """Search using ChromaDB's built-in embedding (fallback)."""
        if self.collection.count() == 0:
            return []

        kwargs = {
            "query_texts": [query],
            "n_results": min(n_results, self.collection.count()),
        }
        if filter_dict:
            kwargs["where"] = filter_dict

        results = self.collection.query(**kwargs)

        search_results = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                score = 1.0 - (results["distances"][0][i] if results["distances"] else 0)
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                search_results.append(
                    SearchResult(text=doc, score=score, metadata=metadata)
                )

        return search_results

    def delete_by_source(self, source_name: str) -> None:
        """Delete all chunks from a specific source."""
        self.collection.delete(where={"source_name": source_name})

    def clear_all(self) -> None:
        """Delete every chunk while keeping the collection object valid for all holders.

        Deletes by IDs rather than dropping the collection so that the MCP server's
        separate ChromaVectorStore instance (which holds its own reference to
        self.collection) is not left with a stale pointer to a deleted collection.
        """
        all_ids = self.collection.get(include=[])["ids"]
        if all_ids:
            self.collection.delete(ids=all_ids)

    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        count = self.collection.count()
        return {
            "total_chunks": count,
            "collection_name": self.COLLECTION_NAME,
            "persist_dir": self.persist_dir,
        }
