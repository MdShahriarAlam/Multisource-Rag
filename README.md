# Multisource RAG

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/framework-FastAPI-009688)
![OpenAI](https://img.shields.io/badge/LLM-OpenAI%20GPT--4o-412991)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

A hybrid RAG (Retrieval-Augmented Generation) chatbot that queries multiple structured databases, cloud storage buckets, and document stores in a single natural-language pipeline. Ask a question — the system classifies it, runs SQL and/or vector search in parallel across all enabled sources, merges results within LLM token limits, and returns a cited answer.

## Architecture

```
User Query (natural language)
         │
  ┌──────▼──────┐
  │  Orchestrator│  ← agentic tool-calling loop (OpenAI function calling)
  │  (GPT-4o)   │
  └──────┬──────┘
         │  routes to one or both:
   ┌─────┴──────┐
   │             │
   ▼             ▼
Structured    Unstructured
Retriever     Retriever
(Text-to-SQL) (ChromaDB vector search)
   │             │
   └─────┬───────┘
         ▼
   Result Merger
   (token-budgeted context assembly)
         │
         ▼
   GPT-4o generates
   answer with citations
```

The orchestrator is a real agentic loop (up to 15 iterations). Each connected data source registers itself as an MCP tool. The agent calls whichever tools are relevant, inspects schemas, generates SQL, and searches embeddings until it has enough context to answer.

## Features

- **Hybrid retrieval** — text-to-SQL (structured) + vector search (unstructured) in one pipeline
- **8 data source connectors** — PostgreSQL, MySQL, BigQuery, Azure SQL, Azure Blob Storage, Azure Cosmos DB, Google Cloud Storage, local file uploads
- **Plugin architecture** — add a connector with a single `@register("type")` decorator and a YAML entry
- **Document ingestion pipeline** — parse (PDF, DOCX, CSV, Excel, JSON, TXT) → chunk (token-based) → embed (OpenAI) → store (ChromaDB)
- **Token-budgeted context merging** — combines SQL tables and document excerpts without exceeding LLM context limits
- **Conversational memory** — per-session history for multi-turn queries
- **MCP server** — separate service on `:8001` that exposes dynamic tools per data source
- **React frontend** — Fluent Design dark UI with acrylic sidebar, chat bubbles, source citations, reasoning viewer
- **Streamlit UI** — lightweight alternative interface

## Supported Data Sources

| Type | Connector | Notes |
|------|-----------|-------|
| `postgresql` | PostgreSQL | Async queries, schema introspection |
| `mysql` | MySQL | PyMySQL, parameterized SQL |
| `bigquery` | Google BigQuery | Service account auth, dataset-scoped |
| `azure_sql` | Azure SQL Database | ODBC Driver 18, T-SQL |
| `azure_blob` | Azure Blob Storage | Ingests PDF, DOCX, CSV, Excel, JSON, TXT |
| `azure_cosmos` | Azure Cosmos DB | Cross-partition queries, schema inference |
| `gcs` | Google Cloud Storage | Same file types as Azure Blob |
| `local_file` | Local uploads | Files dropped in `uploaded_files/` |

## Prerequisites

- Python 3.11+
- Node.js 18+ and npm (React frontend only)
- [Poetry](https://python-poetry.org/) package manager
- OpenAI API key
- At least one data source configured in `sources.yaml`

## Quick Start

```bash
# 1. Clone
git clone <repo-url>
cd Multisource-Rag

# 2. Configure environment
cp .env.example .env
# Edit .env — fill in OPENAI_API_KEY and any source credentials

# 3. Configure data sources
# Edit sources.yaml — set enabled: true for each source you want to use

# 4. Install Python dependencies
poetry install
poetry shell

# 5. Install frontend dependencies (first time only)
cd frontend && npm install && cd ..
```

## Running

Start three services in separate terminals:

```bash
# Terminal 1 — MCP server (data access layer)
python -m src.mcp_server.server
# → http://localhost:8001

# Terminal 2 — API server
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
# → http://localhost:8000  (Swagger UI at /docs)

# Terminal 3 — React frontend
cd frontend && npm run dev
# → http://localhost:5173
```

Open **http://localhost:5173**.

### Alternative: Streamlit

```bash
streamlit run streamlit_app.py
# → http://localhost:8501
```

## Configuration

### Environment variables (`.env`)

Copy `.env.example` to `.env` and fill in values. All variables and their purpose are documented in `.env.example`. Never commit `.env`.

### Data sources (`sources.yaml`)

Each source entry follows this pattern — credentials come from `.env` via `${VAR}` expansion:

```yaml
sources:
  - name: company_postgres
    type: postgresql
    enabled: true
    connection:
      host: ${POSTGRES_HOST}
      port: ${POSTGRES_PORT}
      database: ${POSTGRES_DB}
      user: ${POSTGRES_USER}
      password: ${POSTGRES_PASSWORD}

  - name: azure_documents
    type: azure_blob
    enabled: false
    connection:
      connection_string: ${AZURE_STORAGE_CONNECTION_STRING}
      container_name: documents
```

Disable a source by setting `enabled: false` — no restart needed for config-only changes.

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Natural language query through hybrid RAG pipeline |
| `/api/history/{session_id}` | GET | Conversation history for a session |
| `/api/history/{session_id}/clear` | DELETE | Clear session history |
| `/api/sources` | GET | List connected sources and their status |
| `/api/ingest` | POST | Ingest documents from all enabled storage sources |
| `/api/ingest/{source_name}` | POST | Ingest from one source |
| `/api/upload` | POST | Upload a file for local ingestion |
| `/api/stats` | GET | System stats (sessions, vector store, sources) |
| `/health` | GET | Health check |
| `/docs` | GET | Swagger UI |

### Example

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Who were the top customers by revenue last quarter?", "session_id": "demo"}'
```

## Adding a New Connector

1. Create `src/data_sources/my_connector.py`:

```python
from src.data_sources.base import StructuredConnector
from src.data_sources.registry import register

@register("mydb")
class MyDBConnector(StructuredConnector):
    async def connect(self): ...
    async def execute_query(self, query, params=None): ...
    async def get_table_schema(self, table_name): ...
    async def list_tables(self): ...
```

2. Add an entry to `sources.yaml` with `type: mydb`.

3. Set any required env vars in `.env` and restart. The orchestrator and MCP tools pick it up automatically.

## Project Structure

```
src/
├── agents/
│   ├── orchestrator.py           # Agentic tool-calling loop (max 15 iterations)
│   ├── unstructured_retriever.py # ChromaDB vector search
│   └── result_merger.py          # Token-budgeted context assembly
├── data_sources/
│   ├── base.py                   # Abstract connector classes
│   ├── registry.py               # @register plugin registry
│   ├── postgres_connector.py
│   ├── mysql_connector.py
│   ├── bigquery_connector.py
│   ├── azure_sql_connector.py
│   ├── azure_blob_connector.py
│   ├── cosmos_connector.py
│   ├── gcs_connector.py
│   └── local_file_connector.py
├── document_processing/
│   ├── parsers.py                # PDF, DOCX, CSV, Excel, JSON, TXT
│   ├── chunker.py                # Token-based splitting
│   ├── embedder.py               # OpenAI text-embedding-3-small
│   ├── vector_store.py           # ChromaDB wrapper
│   └── ingestion.py              # End-to-end ingestion pipeline
├── mcp_server/
│   ├── server.py                 # MCP server, port 8001
│   ├── tools.py                  # Dynamic tool definitions per source
│   └── handlers.py               # Request handlers
├── models/schemas.py             # Pydantic request/response models
├── config.py                     # Settings, YAML loader, ${VAR} expansion
└── main.py                       # FastAPI entry point

frontend/
├── src/
│   ├── components/               # Sidebar, ChatPanel, DocumentViewer, ReasoningViewer
│   ├── api/                      # Fetch wrappers
│   ├── types/                    # TypeScript types
│   └── App.tsx
└── vite.config.ts                # Dev server + /api proxy → :8000

scripts/                          # Seed scripts for Postgres and MySQL
tests/                            # pytest suite
sources.yaml                      # Data source config (committed, no secrets)
.env.example                      # Environment variable template (committed)
pyproject.toml                    # Python dependencies (Poetry)
```

## Testing

```bash
python -m pytest tests/ -v
```

Tests cover connector registry, all connector types, document parsers, chunking, vector store operations, and result merging.

## Tech Stack

| Layer | Technology |
|-------|------------|
| LLM | OpenAI GPT-4o |
| Embeddings | OpenAI text-embedding-3-small |
| Web framework | FastAPI + Uvicorn |
| React frontend | React 18 + Vite + TypeScript |
| Alt UI | Streamlit |
| Vector store | ChromaDB |
| Token counting | tiktoken |
| Databases | PostgreSQL (psycopg2), MySQL (PyMySQL), Azure SQL (pyodbc) |
| Cloud storage | Azure Blob, Azure Cosmos DB, Google Cloud Storage |
| Document parsing | pypdf, python-docx, openpyxl |
| Data validation | Pydantic v2 |
| Config | YAML + python-dotenv |
| Testing | pytest + pytest-asyncio |

## License

MIT License — see [LICENSE](LICENSE).
