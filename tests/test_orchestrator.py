"""Tests for the result merger."""
import pytest
from src.agents.result_merger import ResultMerger, MergedContext
from src.agents.structured_retriever import StructuredResult
from src.agents.unstructured_retriever import UnstructuredResult
from src.document_processing.vector_store import SearchResult
from src.models.schemas import DataSource


class TestResultMerger:
    def test_merge_structured_only(self):
        merger = ResultMerger()
        structured = StructuredResult(
            data=[
                {"name": "Alice", "revenue": 1000},
                {"name": "Bob", "revenue": 2000},
            ],
            sources=[
                DataSource(source="db1", query="SELECT ...", records=2, execution_time_ms=50)
            ],
        )

        ctx = merger.merge(structured=structured)
        assert "Alice" in ctx.full_context
        assert "Bob" in ctx.full_context
        assert "Database Results" in ctx.full_context
        assert "Document Excerpts" not in ctx.full_context

    def test_merge_unstructured_only(self):
        merger = ResultMerger()
        unstructured = UnstructuredResult(
            chunks=[
                SearchResult(
                    text="Revenue grew 15% in Q3",
                    score=0.9,
                    metadata={"source_name": "reports", "file_path": "q3.pdf"},
                )
            ]
        )

        ctx = merger.merge(unstructured=unstructured)
        assert "Revenue grew" in ctx.full_context
        assert "Document Excerpts" in ctx.full_context
        assert "Database Results" not in ctx.full_context

    def test_merge_hybrid(self):
        merger = ResultMerger()
        structured = StructuredResult(
            data=[{"metric": "revenue", "value": 1000000}]
        )
        unstructured = UnstructuredResult(
            chunks=[
                SearchResult(
                    text="The forecast predicted 900K revenue",
                    score=0.85,
                    metadata={"file_path": "forecast.pdf"},
                )
            ]
        )

        ctx = merger.merge(structured=structured, unstructured=unstructured)
        assert "Database Results" in ctx.full_context
        assert "Document Excerpts" in ctx.full_context
        assert "revenue" in ctx.full_context.lower()

    def test_merge_empty(self):
        merger = ResultMerger()
        ctx = merger.merge()
        assert ctx.full_context.strip() == ""

    def test_merge_truncates_long_data(self):
        merger = ResultMerger()
        merger.MAX_CONTEXT_TOKENS = 100  # very small budget

        big_data = [{"col": f"value_{i}"} for i in range(1000)]
        structured = StructuredResult(data=big_data)

        ctx = merger.merge(structured=structured)
        assert "truncated" in ctx.full_context.lower()
