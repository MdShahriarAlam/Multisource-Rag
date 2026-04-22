"""Tests for document processing pipeline."""
import pytest
from src.document_processing.parsers import (
    CSVParser,
    JSONParser,
    ParserFactory,
    TextParser,
)
from src.document_processing.chunker import DocumentChunk, TextChunker
from src.document_processing.vector_store import ChromaVectorStore


class TestParsers:
    def test_text_parser(self):
        parser = TextParser()
        result = parser.parse(b"Hello, world!", "test.txt")
        assert len(result) == 1
        assert result[0]["text"] == "Hello, world!"

    def test_text_parser_empty(self):
        parser = TextParser()
        result = parser.parse(b"   ", "test.txt")
        assert len(result) == 0

    def test_csv_parser(self):
        csv_data = b"name,age\nAlice,30\nBob,25\n"
        parser = CSVParser()
        result = parser.parse(csv_data, "test.csv")
        assert len(result) >= 1
        assert "Alice" in result[0]["text"]
        assert "name" in result[0]["text"]

    def test_json_parser_object(self):
        json_data = b'{"key": "value", "count": 42}'
        parser = JSONParser()
        result = parser.parse(json_data, "test.json")
        assert len(result) == 1
        assert "value" in result[0]["text"]

    def test_json_parser_array(self):
        json_data = b'[{"id": 1}, {"id": 2}]'
        parser = JSONParser()
        result = parser.parse(json_data, "test.json")
        assert len(result) >= 1

    def test_parser_factory(self):
        parser = ParserFactory.get_parser("document.txt")
        assert isinstance(parser, TextParser)

    def test_parser_factory_csv(self):
        parser = ParserFactory.get_parser("data.csv")
        assert isinstance(parser, CSVParser)

    def test_parser_factory_unknown(self):
        with pytest.raises(ValueError, match="No parser"):
            ParserFactory.get_parser("file.xyz")

    def test_supported_extensions(self):
        exts = ParserFactory.supported_extensions()
        assert ".pdf" in exts
        assert ".csv" in exts
        assert ".json" in exts
        assert ".txt" in exts


class TestChunker:
    def test_short_text_single_chunk(self):
        chunker = TextChunker(chunk_size=100, chunk_overlap=10)
        chunks = chunker.chunk("Short text.")
        assert len(chunks) == 1
        assert chunks[0].text == "Short text."

    def test_long_text_multiple_chunks(self):
        chunker = TextChunker(chunk_size=10, chunk_overlap=2)
        long_text = "word " * 100  # ~100 tokens
        chunks = chunker.chunk(long_text)
        assert len(chunks) > 1

    def test_chunk_metadata(self):
        chunker = TextChunker(chunk_size=100)
        chunks = chunker.chunk("Hello", {"source_name": "test"})
        assert chunks[0].metadata["source_name"] == "test"

    def test_chunk_id(self):
        chunk = DocumentChunk(
            text="test",
            metadata={"source_name": "src", "file_path": "file.txt"},
            chunk_index=0,
        )
        assert chunk.id == "src:file.txt:chunk_0"

    def test_empty_text(self):
        chunker = TextChunker()
        assert chunker.chunk("") == []
        assert chunker.chunk("   ") == []

    def test_chunk_segments(self):
        chunker = TextChunker(chunk_size=100)
        segments = [
            {"text": "Segment one.", "page_number": "1"},
            {"text": "Segment two.", "page_number": "2"},
        ]
        chunks = chunker.chunk_segments(segments, {"source_name": "test"})
        assert len(chunks) == 2
        assert chunks[0].metadata["source_name"] == "test"
        assert chunks[0].chunk_index == 0
        assert chunks[1].chunk_index == 1


class TestVectorStore:
    def test_add_and_search(self, temp_chroma_dir):
        store = ChromaVectorStore(persist_dir=temp_chroma_dir)

        chunks = [
            DocumentChunk(
                text="The revenue grew by 15% in Q3.",
                metadata={"source_name": "reports", "file_path": "q3.pdf"},
                chunk_index=0,
            ),
            DocumentChunk(
                text="Customer satisfaction score is 4.5 out of 5.",
                metadata={"source_name": "reports", "file_path": "survey.pdf"},
                chunk_index=1,
            ),
        ]
        # Use simple fake embeddings (same dimension)
        embeddings = [[0.1] * 384, [0.9] * 384]

        count = store.add_documents(chunks, embeddings)
        assert count == 2

        stats = store.get_stats()
        assert stats["total_chunks"] == 2

    def test_search_empty_store(self, temp_chroma_dir):
        store = ChromaVectorStore(persist_dir=temp_chroma_dir)
        results = store.search_by_text("anything")
        assert results == []

    def test_delete_by_source(self, temp_chroma_dir):
        store = ChromaVectorStore(persist_dir=temp_chroma_dir)

        chunks = [
            DocumentChunk(
                text="Test chunk",
                metadata={"source_name": "src1"},
                chunk_index=0,
            )
        ]
        store.add_documents(chunks, [[0.5] * 384])
        assert store.get_stats()["total_chunks"] == 1

        store.delete_by_source("src1")
        assert store.get_stats()["total_chunks"] == 0
