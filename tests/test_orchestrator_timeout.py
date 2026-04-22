"""Orchestrator wall-clock timeout enforcement."""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.agents.orchestrator import AgentOrchestrator
from src.config import settings
from src.errors import TimeoutExceeded
from src.mcp_server.handlers import MCPHandler
from src.models.schemas import ChatRequest


@pytest.mark.asyncio
async def test_orchestrator_timeout_fires(mock_registry, monkeypatch):
    monkeypatch.setattr(settings, "request_timeout_seconds", 1)

    handler = MCPHandler(mock_registry)
    orch = AgentOrchestrator(handler)
    orch._tools_cache = []

    async def slow_run(req):
        await asyncio.sleep(5)
        raise AssertionError("should have been cancelled")

    with patch.object(orch, "_run_loop", side_effect=slow_run):
        with pytest.raises(TimeoutExceeded):
            await orch.process_chat(
                ChatRequest(message="hi", session_id="t1")
            )


@pytest.mark.asyncio
async def test_orchestrator_rejects_missing_handler():
    with pytest.raises(ValueError):
        AgentOrchestrator(None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_session_history_lru_cap(mock_registry, monkeypatch):
    monkeypatch.setattr(settings, "max_sessions", 3)
    monkeypatch.setattr(settings, "max_turns_per_session", 2)

    handler = MCPHandler(mock_registry)
    orch = AgentOrchestrator(handler)

    for i in range(5):
        orch.conversation_history.append_turn(f"s{i}", "user", f"msg{i}")
        orch.conversation_history.append_turn(f"s{i}", "assistant", f"reply{i}")

    assert len(orch.conversation_history) == 3
    # Oldest sessions evicted
    assert "s0" not in orch.conversation_history
    assert "s4" in orch.conversation_history


@pytest.mark.asyncio
async def test_session_history_caps_turns(mock_registry, monkeypatch):
    monkeypatch.setattr(settings, "max_turns_per_session", 2)
    handler = MCPHandler(mock_registry)
    orch = AgentOrchestrator(handler)

    for i in range(5):
        orch.conversation_history.append_turn("s", "user", f"u{i}")
        orch.conversation_history.append_turn("s", "assistant", f"a{i}")

    history = orch.get_conversation_history("s")
    # 2 turns = 4 entries max
    assert len(history) == 4
    assert history[0]["content"] == "u3"
