"""Ingestion pipeline — concurrent calls must not corrupt state file."""
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.data_sources.registry import ConnectorRegistry
from src.document_processing.ingestion import IngestionPipeline
from tests.conftest import MockStorageConnector


@pytest.mark.asyncio
async def test_concurrent_ingest_serialized(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    registry = ConnectorRegistry()
    registry._connectors["a"] = MockStorageConnector(name="a")
    registry._connectors["b"] = MockStorageConnector(name="b")

    vector_store = MagicMock()
    vector_store.get_stats.return_value = {"total_chunks": 0}
    vector_store.add_documents = MagicMock()

    embedder = MagicMock()
    embedder.embed_chunks = AsyncMock(return_value=[[0.1] * 8, [0.1] * 8])

    pipeline = IngestionPipeline(
        registry=registry,
        vector_store=vector_store,
        embedder=embedder,
    )

    a, b = await asyncio.gather(
        pipeline.ingest_source("a"),
        pipeline.ingest_source("b"),
    )

    assert a["source"] == "a"
    assert b["source"] == "b"

    state_path = Path(pipeline.STATE_FILE)
    assert state_path.exists()
    data = json.loads(state_path.read_text())
    assert "a" in data["sources"]
    assert "b" in data["sources"]


@pytest.mark.asyncio
async def test_state_write_atomic(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    registry = ConnectorRegistry()
    pipeline = IngestionPipeline(
        registry=registry,
        vector_store=MagicMock(get_stats=MagicMock(return_value={"total_chunks": 0})),
        embedder=MagicMock(),
    )
    pipeline._state = {"sources": {"x": {"f.txt": {"chunks": 1}}}}
    pipeline._save_state()

    # tmp file should not linger after successful write
    assert not Path(pipeline.STATE_FILE + ".tmp").exists()
    data = json.loads(Path(pipeline.STATE_FILE).read_text())
    assert data["sources"]["x"]["f.txt"]["chunks"] == 1
