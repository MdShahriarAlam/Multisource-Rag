"""Main FastAPI application for the multi-source RAG chatbot."""
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import load_sources_config, settings
from .data_sources.registry import ConnectorRegistry
from .document_processing.ingestion import IngestionPipeline
from .document_processing.vector_store import ChromaVectorStore
from .models.schemas import ChatRequest, ChatResponse, IngestionStatus
from .agents import AgentOrchestrator

# Import connectors to trigger @register decorators
import src.data_sources  # noqa: F401

# Global state
orchestrator: AgentOrchestrator = None
ingestion_pipeline: IngestionPipeline = None
registry: ConnectorRegistry = None
_mcp_thread: threading.Thread = None


def _run_mcp_server():
    """Run the MCP server in a background thread (no reload — lives inside main process)."""
    uvicorn.run(
        "src.mcp_server.server:app",
        host=settings.mcp_server_host,
        port=settings.mcp_server_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator, ingestion_pipeline, registry, _mcp_thread

    # Start MCP server in a background daemon thread
    _mcp_thread = threading.Thread(target=_run_mcp_server, daemon=True, name="mcp-server")
    _mcp_thread.start()
    print(f"MCP server starting on http://{settings.mcp_server_host}:{settings.mcp_server_port}")

    # Build registry
    registry = ConnectorRegistry()
    sources = load_sources_config()
    registry.load_from_config(sources)

    # Initialize orchestrator
    orchestrator = AgentOrchestrator()

    # Initialize ingestion pipeline
    ingestion_pipeline = IngestionPipeline(registry)

    # Auto-ingest any files already sitting in the uploaded_files/ folder
    # so they are searchable without requiring a manual upload trigger.
    upload_dir = Path("./uploaded_files")
    if upload_dir.exists() and any(upload_dir.iterdir()):
        print("Auto-ingesting files in uploaded_files/ ...")
        result = await ingestion_pipeline.ingest_source("local_uploads")
        processed = result.get("files_processed", 0)
        skipped   = result.get("files_skipped", 0)
        chunks    = result.get("chunks_created", 0)
        print(f"  -> {processed} file(s) processed, {skipped} skipped, {chunks} chunks indexed")

    print("=" * 60)
    print("Multi-Source RAG Chatbot v2.0")
    print("=" * 60)
    print(f"OpenAI Model: {settings.openai_model}")
    print(f"Sources loaded: {len(registry.get_all())}")
    for info in registry.list_sources():
        print(f"  - {info['name']} ({info['type']})")
    print(f"MCP Server: http://{settings.mcp_server_host}:{settings.mcp_server_port}")
    print(f"Chatbot API: http://{settings.app_host}:{settings.app_port}")
    print("=" * 60)

    yield

    # MCP thread is a daemon — it exits automatically when the main process exits
    print("Shutting down...")


app = FastAPI(
    title="Multi-Source RAG Chatbot",
    description="Hybrid RAG chatbot with multi-source data retrieval",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
async def chat(request: ChatRequest):
    """Process a chat message through the hybrid RAG pipeline."""
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    try:
        # If the user attached a file, prepend a directive so the agent searches
        # that document first, then cross-references the connected databases.
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
            return await orchestrator.process_chat(augmented)
        return await orchestrator.process_chat(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing chat: {e}")


@app.get("/api/history/{session_id}")
async def get_history(session_id: str):
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    history = orchestrator.get_conversation_history(session_id)
    return {"session_id": session_id, "history": history, "message_count": len(history)}


@app.delete("/api/history/{session_id}/clear")
async def clear_history(session_id: str):
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    orchestrator.clear_conversation_history(session_id)
    return {"session_id": session_id, "status": "cleared"}


@app.get("/api/sources")
async def list_sources():
    """List all connected data sources."""
    if not registry:
        return {"sources": []}
    return {"sources": registry.list_sources()}


@app.post("/api/ingest")
async def ingest_all():
    """Trigger document ingestion from all storage sources."""
    if not ingestion_pipeline:
        raise HTTPException(status_code=500, detail="Ingestion pipeline not initialized")
    results = await ingestion_pipeline.ingest_all()
    return {"status": "completed", "results": results}


@app.post("/api/ingest/{source_name}")
async def ingest_source(source_name: str):
    """Trigger document ingestion from a single storage source."""
    if not ingestion_pipeline:
        raise HTTPException(status_code=500, detail="Ingestion pipeline not initialized")
    result = await ingestion_pipeline.ingest_source(source_name)
    return {"status": "completed", "result": result}


@app.get("/api/ingest/status", response_model=IngestionStatus)
async def ingest_status():
    """Get ingestion pipeline status."""
    if not ingestion_pipeline:
        return IngestionStatus()
    return IngestionStatus(**ingestion_pipeline.get_status())


_UPLOAD_DIR = Path("./uploaded_files")
_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv", ".xlsx", ".json"}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a document to the local uploads folder and ingest it immediately."""
    if not ingestion_pipeline:
        raise HTTPException(status_code=500, detail="Ingestion pipeline not initialized")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {sorted(_ALLOWED_EXTENSIONS)}",
        )

    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = _UPLOAD_DIR / file.filename
    content = await file.read()
    dest.write_bytes(content)

    # Clear ingestion state for this file so it is always re-processed
    state = ingestion_pipeline._state.setdefault("sources", {}).setdefault("local_uploads", {})
    state.pop(file.filename, None)
    ingestion_pipeline._save_state()

    result = await ingestion_pipeline.ingest_source("local_uploads")
    chunks_created = result.get("chunks_created", 0)

    return {
        "status": "ingested",
        "filename": file.filename,
        "chunks_created": chunks_created,
    }


@app.get("/api/upload/files")
async def list_uploaded_files():
    """List files in the local upload folder."""
    if not _UPLOAD_DIR.exists():
        return {"files": []}

    files = []
    for path in sorted(_UPLOAD_DIR.iterdir()):
        if path.is_file() and path.suffix.lower() in _ALLOWED_EXTENSIONS:
            stat = path.stat()
            files.append({"name": path.name, "size": stat.st_size})
    return {"files": files}


@app.delete("/api/upload/{filename}")
async def delete_uploaded_file(filename: str):
    """Remove an uploaded file from disk. Vector embeddings are kept in ChromaDB."""
    target = _UPLOAD_DIR / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found")

    target.unlink()
    return {"status": "deleted", "filename": filename, "vectors": "preserved"}


@app.post("/api/vector/clear")
async def clear_vector_store():
    """Wipe all vector embeddings from ChromaDB, reset ingestion state, and delete uploaded files."""
    if not ingestion_pipeline:
        raise HTTPException(status_code=500, detail="Ingestion pipeline not initialized")

    # Clear ChromaDB
    ingestion_pipeline.vector_store.clear_all()
    ingestion_pipeline._state = {"sources": {}}
    ingestion_pipeline._save_state()

    # Delete all files from the upload folder so they don't get re-indexed on next startup
    deleted_files = []
    if _UPLOAD_DIR.exists():
        for f in _UPLOAD_DIR.iterdir():
            if f.is_file() and f.suffix.lower() in _ALLOWED_EXTENSIONS:
                f.unlink()
                deleted_files.append(f.name)

    return {"status": "cleared", "chunks_remaining": 0, "files_deleted": deleted_files}


@app.get("/api/stats")
async def get_stats():
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    total_sessions = len(orchestrator.conversation_history)
    total_messages = sum(len(h) for h in orchestrator.conversation_history.values())
    vector_stats = ChromaVectorStore().get_stats() if ingestion_pipeline else {}
    return {
        "total_sessions": total_sessions,
        "total_messages": total_messages,
        "vector_store": vector_stats,
        "connected_sources": len(registry.get_all()) if registry else 0,
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "chatbot-api",
        "sources": len(registry.get_all()) if registry else 0,
    }


def main():
    uvicorn.run(
        "src.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
