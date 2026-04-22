"""Result merger — combines structured and unstructured retrieval results."""
import json
from typing import Any, Dict, List, Optional

import tiktoken

from .structured_retriever import StructuredResult
from .unstructured_retriever import UnstructuredResult


class MergedContext:
    """Combined context from structured and unstructured retrieval."""

    def __init__(self):
        self.structured_text: str = ""
        self.unstructured_text: str = ""
        self.total_tokens: int = 0

    @property
    def full_context(self) -> str:
        parts = []
        if self.structured_text:
            parts.append(f"## Database Results\n{self.structured_text}")
        if self.unstructured_text:
            parts.append(f"## Document Excerpts\n{self.unstructured_text}")
        return "\n\n".join(parts)


class ResultMerger:
    """Merges structured SQL results and unstructured document chunks."""

    MAX_CONTEXT_TOKENS = 6000  # Leave room for system prompt + response

    def __init__(self, encoding_name: str = "cl100k_base"):
        self.encoding = tiktoken.get_encoding(encoding_name)

    def merge(
        self,
        structured: Optional[StructuredResult] = None,
        unstructured: Optional[UnstructuredResult] = None,
    ) -> MergedContext:
        """Merge results into a single context for the LLM."""
        ctx = MergedContext()
        budget = self.MAX_CONTEXT_TOKENS

        # Allocate tokens: split budget between structured and unstructured
        has_structured = structured and structured.data
        has_unstructured = unstructured and unstructured.chunks

        if has_structured and has_unstructured:
            structured_budget = budget // 2
            unstructured_budget = budget - structured_budget
        elif has_structured:
            structured_budget = budget
            unstructured_budget = 0
        else:
            structured_budget = 0
            unstructured_budget = budget

        # Format structured data as markdown table
        if has_structured:
            ctx.structured_text = self._format_structured(
                structured.data, structured_budget
            )

        # Format unstructured chunks
        if has_unstructured:
            ctx.unstructured_text = self._format_unstructured(
                unstructured.chunks, unstructured_budget
            )

        ctx.total_tokens = len(self.encoding.encode(ctx.full_context))
        return ctx

    def _format_structured(
        self, data: List[Dict[str, Any]], token_budget: int
    ) -> str:
        """Format SQL results as a readable markdown table."""
        if not data:
            return ""

        # Get column headers from first record
        columns = list(data[0].keys())
        # Filter out internal columns
        columns = [c for c in columns if not c.startswith("_")]

        lines = []
        header = "| " + " | ".join(columns) + " |"
        separator = "| " + " | ".join("---" for _ in columns) + " |"
        lines.append(header)
        lines.append(separator)

        for row in data:
            values = [str(row.get(c, ""))[:50] for c in columns]
            lines.append("| " + " | ".join(values) + " |")

            # Check token budget
            current_text = "\n".join(lines)
            if len(self.encoding.encode(current_text)) > token_budget:
                lines.pop()
                lines.append(f"\n*({len(data) - len(lines) + 2} more rows truncated)*")
                break

        return "\n".join(lines)

    def _format_unstructured(
        self, chunks: list, token_budget: int
    ) -> str:
        """Format document chunks with source attribution."""
        if not chunks:
            return ""

        parts = []
        tokens_used = 0

        for i, chunk in enumerate(chunks):
            source = chunk.metadata.get("source_name", "unknown")
            file_path = chunk.metadata.get("file_path", "unknown")
            score = f"{chunk.score:.2f}"

            entry = (
                f"**[{file_path}]** (relevance: {score})\n"
                f"> {chunk.text}\n"
            )

            entry_tokens = len(self.encoding.encode(entry))
            if tokens_used + entry_tokens > token_budget:
                remaining = len(chunks) - i
                parts.append(f"\n*({remaining} more excerpts truncated)*")
                break

            parts.append(entry)
            tokens_used += entry_tokens

        return "\n".join(parts)
