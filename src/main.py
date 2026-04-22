"""FastAPI application — multi-source RAG chatbot."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .agents import AgentOrchestrator
from .config import load_sources_config, settings
from .data_sources.registry import ConnectorRegistry
from .document_processing.ingestion import IngestionPipeline
from .errors import (
    FileNotFound,
    InvalidInput,
    NotInitialized,
    PathTraversal,
    RAGError,
    rag_error_handler,
    unhandled_exception_handler,
)
from .logging_config import configure_logging
from .mcp_server.handlers import MCPHandler
from .models.schemas import ChatRequest, ChatResponse, IngestionStatus, SourceStatus

# Trigger @register decorators
import src.data_sources  # noqa: F401

configure_logging()
log = logging.getLogger(__name__)


# ── Application state ───────────────────────────────────────────────────────

class AppState:
    registry: Optional[ConnectorRegistry] = None
    handler: Optional[MCPHandler] = None
    orchestrator: Optional[AgentOrchestrator] = None
    ingestion_pipeline: Optional[IngestionPipeline] = None
    source_health: dict[str, bool] = {}


state = AppState()


def _upload_dir() -> Path:
    return Path(settings.upload_dir).resolve()


def _safe_upload_path(filename: str) -> Path:
    """Reject traversal: keep basename only, ensure result stays inside upload_dir."""
    if not filename or filename in (".", ".."):
        raise PathTraversal("Invalid filename", details={"filename": filename})
    base = Path(filename).name
    if not base or base != filename or ".." in base:
        raise PathTraversal("Filename must not contain path separators", details={"filename": filename})
    root = _upload_dir()
    root.mkdir(parents=True, exist_ok=True)
    candidate = (root / base).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as e:
        raise PathTraversal("Path escapes upload directory", details={"filename": filename}) from e
    return candidate


# ── Lifespan ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting Multi-Source RAG Chatbot v2.0 (env=%s)", settings.env)

    # Build registry + load sources
    state.registry = ConnectorRegistry()
    try:
        sources = load_sources_config()
    except Exception:
        log.exception("Failed to load sources.yaml")
        sources = []
    state.registry.load_from_config(sources)

    # Fail-soft connect — app starts even if individual sources are down
    results = await state.registry.connect_all()
    state.source_health = results
    for name, ok in results.items():
        if ok:
            log.info("Connected source: %s", name)
        else:
            log.warning("Source degraded (connect failed): %s", name)

    # In-process MCP handler + orchestrator (no HTTP hop, no daemon thread)
    state.handler = MCPHandler(state.registry)
    state.orchestrator = AgentOrchestrator(state.handler)

    state.ingestion_pipeline = IngestionPipeline(state.registry)

    # Auto-ingest files sitting in upload dir so they are searchable on boot
    upload_dir = _upload_dir()
    if upload_dir.exists() and any(upload_dir.iterdir()):
        log.info("Auto-ingesting files in %s", upload_dir)
        try:
            result = await state.ingestion_pipeline.ingest_source("local_uploads")
            log.info(
                "Auto-ingest done: %d processed, %d skipped, %d chunks",
                result.get("files_processed", 0),
                result.get("files_skipped", 0),
                result.get("chunks_created", 0),
            )
        except Exception:
            log.exception("Auto-ingest failed")

    log.info("Model=%s  sources=%d", settings.openai_model, len(state.registry.get_all()))

    yield

    log.info("Shutting down — disconnecting sources")
    if state.registry is not None:
        await state.registry.disconnect_all()


# ── App construction ────────────────────────────────────────────────────────

app = FastAPI(
    title="Multi-Source RAG Chatbot",
    description="Hybrid RAG chatbot with multi-source data retrieval",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

app.add_exception_handler(RAGError, rag_error_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _require_orchestrator() -> AgentOrchestrator:
    if state.orchestrator is None:
        raise NotInitialized("Orchestrator not initialized")
    return state.orchestrator


def _require_pipeline() -> IngestionPipeline:
    if state.ingestion_pipeline is None:
        raise NotInitialized("Ingestion pipeline not initialized")
    return state.ingestion_pipeline


def _require_registry() -> ConnectorRegistry:
    if state.registry is None:
        raise NotInitialized("Registry not initialized")
    return state.registry


# ── Routes ──────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "name": "Multi-Source RAG Chatbot",
        "version": "2.0.0",
        "endpoints": {
            "chat": "/api/chat",
            "history": "/api/history/{session_id}",
            "sources": "/api/sources",
            "ingest": "/api/ingest",
            "ingest_status": "/api/ingest/status",
            "health": "/health",
        },
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    orch = _require_orchestrator()
    if request.context and request.context.get("uploaded_file"):
        filename = request.context["uploaded_file"]
        prefix = (
            f"IMPORTANT: The user has just uploaded '{filename}'. "
            f"Your FIRST tool call MUST be: search_documents(query='invoice customer order details products') "
            f"— do NOT call list_files or list_tables first. "
            f"After reading the document content, extract all key fields "
            f"(customer name, email, order ID, product IDs, amounts, dates), "
            f"then query the SQL databases to find matching records and cross-reference. "
            f"Combine both sources into one coherent answer.\n\n"
            f"User question: "
        )
        augmented = request.model_copy(update={"message": prefix + request.message})
        return await orch.process_chat(augmented)
    return await orch.process_chat(request)


@app.get("/api/history/{session_id}")
async def get_history(session_id: str):
    orch = _require_orchestrator()
    history = orch.get_conversation_history(session_id)
    return {"session_id": session_id, "history": history, "message_count": len(history)}


@app.delete("/api/history/{session_id}/clear")
async def clear_history(session_id: str):
    orch = _require_orchestrator()
    orch.clear_conversation_history(session_id)
    return {"session_id": session_id, "status": "cleared"}


@app.get("/api/sources")
async def list_sources():
    registry = state.registry
    if registry is None:
        return {"sources": []}
    out = []
    for info in registry.list_sources():
        name = info["name"]
        out.append(
            SourceStatus(
                name=name,
                type=info["type"],
                connector_class=info["connector_class"],
                connected=bool(state.source_health.get(name, False)),
            ).model_dump()
        )
    return {"sources": out}


@app.post("/api/ingest")
async def ingest_all():
    pipeline = _require_pipeline()
    results = await pipeline.ingest_all()
    return {"status": "completed", "results": results}


@app.post("/api/ingest/{source_name}")
async def ingest_source(source_name: str):
    pipeline = _require_pipeline()
    result = await pipeline.ingest_source(source_name)
    return {"status": "completed", "result": result}


@app.get("/api/ingest/status", response_model=IngestionStatus)
async def ingest_status() -> IngestionStatus:
    if state.ingestion_pipeline is None:
        return IngestionStatus()
    return IngestionStatus(**state.ingestion_pipeline.get_status())


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    pipeline = _require_pipeline()

    if not file.filename:
        raise InvalidInput("Missing filename")

    dest = _safe_upload_path(file.filename)
    safe_name = dest.name

    suffix = dest.suffix.lower()
    allowed = settings.allowed_upload_extensions_set
    if suffix not in allowed:
        raise InvalidInput(
            f"Unsupported file type '{suffix}'",
            details={"allowed": sorted(allowed)},
        )

    content = await file.read()
    if len(content) > settings.max_file_bytes:
        raise InvalidInput(
            "File exceeds size limit",
            details={"max_bytes": settings.max_file_bytes, "got_bytes": len(content)},
        )

    dest.write_bytes(content)

    # Force re-ingest: clear state entry for this filename
    src_state = pipeline._state.setdefault("sources", {}).setdefault("local_uploads", {})
    src_state.pop(safe_name, None)

    result = await pipeline.ingest_source("local_uploads")
    return {
        "status": "ingested",
        "filename": safe_name,
        "chunks_created": result.get("chunks_created", 0),
    }


@app.get("/api/upload/files")
async def list_uploaded_files():
    upload_dir = _upload_dir()
    if not upload_dir.exists():
        return {"files": []}

    allowed = settings.allowed_upload_extensions_set
    files = []
    for path in sorted(upload_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in allowed:
            stat = path.stat()
            files.append({"name": path.name, "size": stat.st_size})
    return {"files": files}


@app.delete("/api/upload/{filename}")
async def delete_uploaded_file(filename: str):
    target = _safe_upload_path(filename)
    if not target.exists():
        raise FileNotFound(f"File '{target.name}' not found")
    target.unlink()
    return {"status": "deleted", "filename": target.name, "vectors": "preserved"}


@app.post("/api/vector/clear")
async def clear_vector_store():
    pipeline = _require_pipeline()
    pipeline.vector_store.clear_all()
    pipeline._state = {"sources": {}}
    pipeline._save_state()

    deleted_files = []
    upload_dir = _upload_dir()
    allowed = settings.allowed_upload_extensions_set
    if upload_dir.exists():
        for f in upload_dir.iterdir():
            if f.is_file() and f.suffix.lower() in allowed:
                f.unlink()
                deleted_files.append(f.name)

    return {"status": "cleared", "chunks_remaining": 0, "files_deleted": deleted_files}


@app.get("/api/stats")
async def get_stats():
    orch = _require_orchestrator()
    registry = _require_registry()
    total_sessions = len(orch.conversation_history)
    total_messages = sum(len(h) for h in orch.conversation_history.values())
    vector_stats = (
        state.ingestion_pipeline.vector_store.get_stats()
        if state.ingestion_pipeline is not None
        else {}
    )
    return {
        "total_sessions": total_sessions,
        "total_messages": total_messages,
        "vector_store": vector_stats,
        "connected_sources": sum(1 for v in state.source_health.values() if v),
        "total_sources": len(registry.get_all()),
    }


@app.get("/health")
async def health_check():
    registry = state.registry
    if registry is None:
        return {"status": "starting", "service": "chatbot-api", "sources": {}}

    per_source = {}
    degraded = False
    for name, conn in registry.get_all().items():
        connected = bool(state.source_health.get(name, False))
        healthy: Optional[bool] = None
        error: Optional[str] = None
        if connected and hasattr(conn, "health_check"):
            try:
                healthy = bool(await conn.health_check())  # type: ignore[attr-defined]
            except Exception as e:
                healthy = False
                error = str(e)
        per_source[name] = {
            "connected": connected,
            "healthy": healthy,
            "error": error,
            "type": conn.source_type,
        }
        if not connected or healthy is False:
            degraded = True

    return {
        "status": "degraded" if degraded else "healthy",
        "service": "chatbot-api",
        "sources": per_source,
    }


def main():
    uvicorn.run(
        "src.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=(settings.env != "prod"),
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
