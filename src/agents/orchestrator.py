"""Agentic orchestrator — OpenAI tool-calling loop using in-process MCP handler."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Set

from openai import AsyncOpenAI

from ..config import settings
from ..errors import InvalidInput, TimeoutExceeded
from ..mcp_server.handlers import MCPHandler
from ..mcp_server.tools import build_tool_definitions
from ..models.schemas import (
    ChatRequest,
    ChatResponse,
    DataSource,
    DocumentSource,
    QueryType,
)

log = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are an expert data analyst agent. You have access to tools for querying \
databases and searching documents. Use them to answer the user's question accurately.

WORKFLOW:
1. If the user mentions a document, PDF, or invoice — call search_documents FIRST with \
relevant keywords to extract the content.
2. Call list_tables for each data source to discover what data is available.
3. Call get_schema on relevant tables to understand their structure.
4. Optionally call get_sample_data to see example rows.
5. Call find_relationships if you need to join data across sources.
6. Call query_{source} tools to execute SQL (SELECT only — DML is blocked server-side).
7. Once you have enough data, answer the user's question directly and clearly.

DOCUMENT RULES:
- search_documents is the ONLY tool that returns document text. list_files returns filenames only.
- When a PDF or document is mentioned, always call search_documents first.
- After extracting info from a document, query the connected SQL databases for matching records.

SQL RULES:
- Each query_{source} tool is connected to a SEPARATE database — never reference tables from \
another source in one SQL query.
- Only SELECT / WITH queries are allowed. If you need to combine sources, query each independently.
- If a query fails, read the error, fix the SQL, and retry — but do not loop forever on the same error.
- Always base answers on actual tool output. Use markdown tables for tabular data."""


class _SessionHistory(OrderedDict):
    """LRU cap on sessions; each value is a list of {role, content} dicts."""

    def __init__(self, max_sessions: int, max_turns: int):
        super().__init__()
        self.max_sessions = max_sessions
        self.max_turns = max_turns

    def append_turn(self, session_id: str, role: str, content: str) -> None:
        history = self.setdefault(session_id, [])
        history.append({"role": role, "content": content})
        # 2 entries per turn (user + assistant)
        if len(history) > self.max_turns * 2:
            del history[: len(history) - self.max_turns * 2]
        self.move_to_end(session_id)
        while len(self) > self.max_sessions:
            self.popitem(last=False)

    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        return list(self.get(session_id, []))

    def setdefault(self, key, default=None):  # type: ignore[override]
        if key in self:
            self.move_to_end(key)
            return self[key]
        super().__setitem__(key, default if default is not None else [])
        return self[key]


class AgentOrchestrator:
    """Agentic loop: LLM decides which tools to call; handler runs in-process."""

    def __init__(self, handler: MCPHandler):
        if handler is None:
            raise ValueError("MCPHandler is required")
        self.handler = handler
        self.openai_client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_request_timeout,
        )
        self.conversation_history = _SessionHistory(
            max_sessions=settings.max_sessions,
            max_turns=settings.max_turns_per_session,
        )
        self._tools_cache: Optional[List[Dict[str, Any]]] = None

    def refresh_tools(self) -> None:
        """Rebuild tool definitions from the registry (call after source changes)."""
        self._tools_cache = build_tool_definitions(self.handler.registry)

    def _get_tools(self) -> List[Dict[str, Any]]:
        if self._tools_cache is None:
            self.refresh_tools()
        mcp_tools = self._tools_cache or []
        openai_tools = []
        for tool in mcp_tools:
            parameters = tool.get("inputSchema") or {"type": "object", "properties": {}}
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": parameters,
                },
            })
        return openai_tools

    async def process_chat(self, request: ChatRequest) -> ChatResponse:
        """Process a user message with a hard wall-clock budget."""
        try:
            return await asyncio.wait_for(
                self._run_loop(request),
                timeout=settings.request_timeout_seconds,
            )
        except asyncio.TimeoutError as e:
            log.warning("Request timeout for session %s", request.session_id)
            raise TimeoutExceeded(
                f"Request exceeded {settings.request_timeout_seconds}s budget",
                details={"session_id": request.session_id},
            ) from e

    async def _run_loop(self, request: ChatRequest) -> ChatResponse:
        tools = self._get_tools()
        messages = self._build_messages(request)

        reasoning_steps: List[str] = []
        data_sources: List[DataSource] = []
        doc_sources: List[DocumentSource] = []
        tools_called: Set[str] = set()
        final_message: Optional[str] = None

        for iteration in range(settings.max_iterations):
            reasoning_steps.append(f"Iter {iteration + 1}: LLM call")
            response = await self.openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                tools=tools or None,
                tool_choice="auto" if tools else None,
            )
            choice = response.choices[0]
            msg = choice.message

            msg_dict: Dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
            if msg.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]
            messages.append(msg_dict)

            if not msg.tool_calls:
                final_message = msg.content or ""
                break

            for tool_call in msg.tool_calls:
                name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments or "{}")
                    if not isinstance(args, dict):
                        raise InvalidInput("Tool arguments must be a JSON object")
                except (json.JSONDecodeError, InvalidInput) as e:
                    log.warning("Malformed tool args for %s: %s", name, e)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({"error": f"Invalid arguments: {e}"}),
                    })
                    continue

                tools_called.add(name)
                reasoning_steps.append(f"{name}({_fmt_args(args)})")

                start = time.time()
                result = await self.handler.handle_tool_call(name, args)
                elapsed_ms = (time.time() - start) * 1000

                # Source-citation tracking
                if name.startswith("query_") and not name.startswith("query_documents_") \
                        and result.get("success"):
                    source_name = name[len("query_"):]
                    data = result.get("data") or []
                    data_sources.append(DataSource(
                        source=source_name,
                        query=args.get("query", ""),
                        records=len(data) if isinstance(data, list) else 0,
                        execution_time_ms=elapsed_ms,
                    ))
                    reasoning_steps.append(
                        f"  → {len(data) if isinstance(data, list) else 0} rows from "
                        f"{source_name} ({elapsed_ms:.0f}ms)"
                    )

                if name == "search_documents" and result.get("success"):
                    for chunk in (result.get("data") or []):
                        meta = chunk.get("metadata") or {}
                        doc_sources.append(DocumentSource(
                            source=meta.get("source_name", meta.get("source", "documents")),
                            file_path=meta.get("file_path", ""),
                            chunk_text=chunk.get("text", "")[:500],
                            relevance_score=chunk.get("score", 0.0),
                        ))

                if not result.get("success"):
                    reasoning_steps.append(f"  → Error: {result.get('error')}")

                tool_content = (
                    result.get("data") if result.get("success")
                    else {"error": result.get("error")}
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_content, default=str),
                })
        else:
            # Loop exhausted without break
            final_message = (
                "I reached the maximum number of reasoning steps without a complete "
                "answer. Please rephrase or narrow your question."
            )
            reasoning_steps.append("max iterations reached")

        if final_message is None:
            final_message = "(no response)"

        # Persist to history (dedup document sources by file_path, keep best score)
        self.conversation_history.append_turn(request.session_id, "user", request.message)
        self.conversation_history.append_turn(request.session_id, "assistant", final_message)

        return ChatResponse(
            response=final_message,
            sources=data_sources,
            document_sources=_dedupe_doc_sources(doc_sources),
            reasoning=" → ".join(reasoning_steps),
            query_type=_infer_query_type(tools_called),
            session_id=request.session_id,
        )

    def _build_messages(self, request: ChatRequest) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.conversation_history.get_history(request.session_id))
        messages.append({"role": "user", "content": request.message})
        return messages

    def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        return self.conversation_history.get_history(session_id)

    def clear_conversation_history(self, session_id: str) -> None:
        self.conversation_history.pop(session_id, None)


def _infer_query_type(tools_called: Set[str]) -> Optional[QueryType]:
    used_sql = any(
        t.startswith("query_") and not t.startswith("query_documents_") for t in tools_called
    )
    used_docs = "search_documents" in tools_called or any(
        t.startswith("query_documents_") for t in tools_called
    )
    if used_sql and used_docs:
        return QueryType.HYBRID
    if used_sql:
        return QueryType.STRUCTURED_ONLY
    if used_docs:
        return QueryType.UNSTRUCTURED_ONLY
    return None


def _dedupe_doc_sources(sources: List[DocumentSource]) -> List[DocumentSource]:
    """Keep one entry per (source, file_path) — the best-scoring chunk."""
    best: Dict[tuple, DocumentSource] = {}
    for s in sources:
        key = (s.source, s.file_path)
        if key not in best or s.relevance_score > best[key].relevance_score:
            best[key] = s
    return list(best.values())


def _fmt_args(args: Dict[str, Any]) -> str:
    parts = []
    for k, v in args.items():
        s = str(v)
        parts.append(f"{k}={s[:60] + '…' if len(s) > 60 else s!r}")
    return ", ".join(parts)
