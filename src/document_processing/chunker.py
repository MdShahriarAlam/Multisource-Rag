"""Text chunking for document processing."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import tiktoken


@dataclass
class DocumentChunk:
    """A chunk of text with metadata for embedding and retrieval."""

    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunk_index: int = 0

    @property
    def id(self) -> str:
        """Generate a stable ID from metadata."""
        source = self.metadata.get("source_name", "unknown")
        file_path = self.metadata.get("file_path", "unknown")
        return f"{source}:{file_path}:chunk_{self.chunk_index}"


class TextChunker:
    """Split text into overlapping chunks based on token count."""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        encoding_name: str = "cl100k_base",
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoding = tiktoken.get_encoding(encoding_name)

    def chunk(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> List[DocumentChunk]:
        """Split text into token-based overlapping chunks."""
        if not text or not text.strip():
            return []

        base_metadata = metadata or {}
        tokens = self.encoding.encode(text)

        if len(tokens) <= self.chunk_size:
            return [
                DocumentChunk(
                    text=text.strip(),
                    metadata={**base_metadata, "total_tokens": len(tokens)},
                    chunk_index=0,
                )
            ]

        chunks = []
        start = 0
        chunk_idx = 0

        while start < len(tokens):
            end = min(start + self.chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = self.encoding.decode(chunk_tokens).strip()

            if chunk_text:
                chunks.append(
                    DocumentChunk(
                        text=chunk_text,
                        metadata={
                            **base_metadata,
                            "chunk_tokens": len(chunk_tokens),
                        },
                        chunk_index=chunk_idx,
                    )
                )
                chunk_idx += 1

            if end >= len(tokens):
                break

            start = end - self.chunk_overlap

        return chunks

    def chunk_segments(
        self,
        segments: List[Dict[str, Any]],
        base_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[DocumentChunk]:
        """Chunk a list of parsed segments (from parsers)."""
        all_chunks = []
        global_idx = 0

        for segment in segments:
            text = segment.pop("text", "")
            segment_meta = {**(base_metadata or {}), **segment}
            sub_chunks = self.chunk(text, segment_meta)

            for c in sub_chunks:
                c.chunk_index = global_idx
                global_idx += 1
            all_chunks.extend(sub_chunks)

        return all_chunks
