"""True agentic orchestrator — OpenAI tool-calling loop over MCP tools."""
import json
import time
from typing import Any, Dict, List, Optional, Set

import httpx
from openai import AsyncOpenAI

from ..config import settings
from ..models.schemas import (
    ChatRequest,
    ChatResponse,
    DataSource,
    DocumentSource,
    QueryType,
)


SYSTEM_PROMPT = """You are an expert data analyst agent. You have access to tools for querying \
databases and searching documents. Use them to answer the user's question accurately.

WORKFLOW:
1. If the user mentions a document, PDF, or invoice — call search_documents FIRST with \
relevant keywords to extract the content.
2. Call list_tables for each data source to discover what data is available.
3. Call get_schema on relevant tables to understand their structure.
4. Optionally call get_sample_data to see example rows.
5. Call find_relationships if you need to join data across sources.
6. Call query_{source} tools to execute SQL and retrieve data.
7. Once you have enough data, answer the user's question directly and clearly.

DOCUMENT RULES — READ CAREFULLY:
- search_documents is the ONLY tool that returns document text/content. \
list_files only returns filenames — it does NOT give you the content.
- When a PDF or document is mentioned, always call search_documents with descriptive \
terms (e.g. "invoice customer name order total products") before doing anything else.
- After extracting info from a document (customer name, order ID, product names), \
use that info to query the connected SQL databases for matching records.
- Never say a document "cannot be found" after only calling list_files. \
If list_files shows a file exists, call search_documents to read its content.

CRITICAL SQL RULES:
- Each query_{source} tool is connected to a SEPARATE database — never reference tables \
from another source in a SQL query.
- If a SQL query fails (error in tool result), read the error, fix the SQL, and retry.
- Be efficient: don't call get_schema for tables that are clearly irrelevant.
- For cross-source questions, query each source independently — the data will be combined.
- Always answer based on actual data returned by tools, not assumptions.
- Format answers in a clear, natural way. Use markdown tables for tabular data."""


class AgentOrchestrator:
    """True agentic loop: LLM autonomously decides which tools to call and when to stop."""

    MAX_ITERATIONS = 15

    def __init__(self):
        self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.mcp_url = f"http://{settings.mcp_server_host}:{settings.mcp_server_port}"
        self.conversation_history: Dict[str, List[Dict[str, Any]]] = {}

    async def process_chat(self, request: ChatRequest) -> ChatResponse:
        """Process a user message through the agentic tool-calling loop."""

        # Fetch tools from MCP server and convert to OpenAI function format
        tools = await self._get_openai_tools()

        # Build messages: system + conversation history + new user message
        messages = self._build_messages(request)

        reasoning_steps: List[str] = []
        data_sources: List[DataSource] = []
        doc_sources: List[DocumentSource] = []
        tools_called: Set[str] = set()
        final_message = None

        for iteration in range(self.MAX_ITERATIONS):
            reasoning_steps.append(f"Iteration {iteration + 1}: calling LLM...")

            response = await self.openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None,
            )

            choice = response.choices[0]
            msg = choice.message

            # Append assistant message to conversation
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

            # If no tool calls — final answer
            if choice.finish_reason == "stop" or not msg.tool_calls:
                final_message = msg.content or ""
                break

            # Execute each tool call
            for tool_call in msg.tool_calls:
                name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                tools_called.add(name)
                reasoning_steps.append(f"Tool: {name}({_fmt_args(args)})")

                start = time.time()
                result = await self._execute_tool(name, args)
                elapsed = (time.time() - start) * 1000

                # Track DB source citations
                if name.startswith("query_") and result.get("success"):
                    source_name = name[len("query_"):]
                    data = result.get("data", [])
                    query_str = args.get("query", "")
                    data_sources.append(
                        DataSource(
                            source=source_name,
                            query=query_str,
                            records=len(data) if isinstance(data, list) else 0,
                            execution_time_ms=elapsed,
                        )
                    )
                    reasoning_steps.append(
                        f"  → {len(data) if isinstance(data, list) else 0} rows from {source_name} ({elapsed:.0f}ms)"
                    )

                # Track document citations
                if name == "search_documents" and result.get("success"):
                    for chunk in (result.get("data") or []):
                        meta = chunk.get("metadata", {})
                        doc_sources.append(
                            DocumentSource(
                                source=meta.get("source", "documents"),
                                file_path=meta.get("file_path", meta.get("source", "")),
                                chunk_text=chunk.get("text", ""),
                                relevance_score=chunk.get("score", 0.0),
                            )
                        )

                if not result.get("success"):
                    reasoning_steps.append(f"  → Error: {result.get('error')}")

                # Append tool result to messages
                content = result.get("data") if result.get("success") else {"error": result.get("error")}
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(content, default=str),
                    }
                )

        if final_message is None:
            final_message = "I reached the maximum number of steps without a complete answer. Please try rephrasing your question."
            reasoning_steps.append("Reached max iterations.")

        # Infer query type from tools used
        query_type = self._infer_query_type(tools_called)

        # Update conversation history (keep last 20 turns)
        history = self.conversation_history.setdefault(request.session_id, [])
        history.append({"role": "user", "content": request.message})
        history.append({"role": "assistant", "content": final_message})
        if len(history) > 40:
            history[:] = history[-40:]

        return ChatResponse(
            response=final_message,
            sources=data_sources,
            document_sources=doc_sources,
            reasoning=" -> ".join(reasoning_steps),
            query_type=query_type,
            session_id=request.session_id,
        )

    # ── Internal helpers ────────────────────────────────────────────────────

    async def _get_openai_tools(self) -> List[Dict[str, Any]]:
        """Fetch tool definitions from MCP server and convert to OpenAI format."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.mcp_url}/tools")
                mcp_tools = resp.json().get("tools", [])
        except Exception as e:
            print(f"Warning: could not fetch MCP tools: {e}")
            return []

        openai_tools = []
        for tool in mcp_tools:
            # MCP uses "inputSchema", OpenAI uses "parameters"
            parameters = tool.get("inputSchema") or tool.get("parameters") or {
                "type": "object",
                "properties": {},
            }
            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": parameters,
                    },
                }
            )
        return openai_tools

    async def _execute_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool via the MCP server."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.mcp_url}/tools/execute",
                    json={"tool_name": name, "parameters": args},
                )
                return resp.json()
        except Exception as e:
            return {"success": False, "data": None, "error": str(e)}

    def _build_messages(self, request: ChatRequest) -> List[Dict[str, Any]]:
        """Build the messages list: system + history + new user message."""
        messages: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Add conversation history (already stored as plain user/assistant turns)
        history = self.conversation_history.get(request.session_id, [])
        messages.extend(history)

        messages.append({"role": "user", "content": request.message})
        return messages

    def _infer_query_type(self, tools_called: Set[str]) -> Optional[QueryType]:
        used_sql = any(t.startswith("query_") and t != "query_documents" for t in tools_called)
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

    def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        return self.conversation_history.get(session_id, [])

    def clear_conversation_history(self, session_id: str) -> None:
        self.conversation_history.pop(session_id, None)


def _fmt_args(args: Dict[str, Any]) -> str:
    """Format tool args for display in reasoning steps (truncate long values)."""
    parts = []
    for k, v in args.items():
        s = str(v)
        parts.append(f"{k}={s[:60] + '…' if len(s) > 60 else s!r}")
    return ", ".join(parts)
