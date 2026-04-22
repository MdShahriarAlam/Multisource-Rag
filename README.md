# Multi-Source Hybrid RAG Chatbot

A hybrid RAG (Retrieval-Augmented Generation) chatbot that retrieves and correlates data across multiple structured databases, cloud storage, and document stores. Ask natural language questions and the system automatically discovers relevant data, generates SQL queries, searches document embeddings, and combines everything into a single coherent answer.

## Features

- **Hybrid Retrieval** — Combines text-to-SQL (structured) and vector search (unstructured) in a single query pipeline
- **6 Data Source Connectors** — PostgreSQL, BigQuery, Azure SQL, Azure Blob Storage, Azure Cosmos DB, Google Cloud Storage
- **Plugin Architecture** — Add new connectors with a single `@register("type")` decorator and a YAML config entry
- **Document Processing Pipeline** — Parse (PDF, DOCX, CSV, Excel, JSON, TXT) → Chunk (token-based) → Embed (OpenAI) → Store (ChromaDB)
- **Query Classification** — LLM classifies each query as structured-only, unstructured-only, or hybrid, then routes accordingly
- **Parallel Retrieval** — Hybrid queries fetch SQL results and document chunks concurrently
- **Token-Budgeted Context Merging** — Combines SQL tables and document excerpts within LLM token limits
- **Conversational Memory** — Maintains per-session conversation history
- **React Frontend** — Fluent Design dark UI with acrylic sidebar, chat bubbles, source citations, and reasoning viewer
- **Streamlit UI** — Alternative lightweight web interface

## Supported Data Sources

| Type | Connector | Description |
|------|-----------|-------------|
| `postgresql` | PostgreSQL | Async queries, schema introspection, parameterized SQL |
| `bigquery` | Google BigQuery | Service account auth, dataset-scoped queries |
| `azure_sql` | Azure SQL Database | ODBC Driver 18, T-SQL support |
| `azure_blob` | Azure Blob Storage | PDF, DOCX, CSV, Excel, JSON, TXT file ingestion |
| `azure_cosmos` | Azure Cosmos DB | Cross-partition queries, schema inference |
| `gcs` | Google Cloud Storage | Same file type support as Azure Blob |

## Prerequisites

- Python 3.11+
- Node.js 18+ and npm (for the React frontend)
- [Poetry](https://python-poetry.org/) package manager
- OpenAI API key
- At least one data source (database or cloud storage) configured

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd Multisource-Rag

# Install dependencies
poetry install

# Activate the virtual environment
poetry shell
```

## Configuration

### 1. Environment Variables (`.env`)

Create a `.env` file in the project root with your credentials:

```env
# Required
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4-turbo-preview

# PostgreSQL (if enabled)
POSTGRES_HOST=localhost
POSTGRES_DB=mydb
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secret

# BigQuery (if enabled)
GCP_PROJECT_ID=my-project
BIGQUERY_DATASET=my_dataset
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# Azure SQL (if enabled)
AZURE_SQL_SERVER=myserver.database.windows.net
AZURE_SQL_DB=mydb
AZURE_SQL_USER=admin
AZURE_SQL_PASSWORD=secret

# Azure Blob Storage (if enabled)
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;...

# Azure Cosmos DB (if enabled)
COSMOS_ENDPOINT=https://myaccount.documents.azure.com:443/
COSMOS_KEY=...
COSMOS_DB=mydb

# Google Cloud Storage (if enabled)
GCS_BUCKET=my-bucket
```

### 2. Data Sources (`sources.yaml`)

Each source is defined in `sources.yaml`. Enable or disable sources by setting `enabled: true/false`. Environment variables are referenced with `${VAR_NAME}` syntax and expanded automatically from `.env`.

```yaml
sources:
  - name: company_postgres
    type: postgresql
    enabled: true
    connection:
      host: ${POSTGRES_HOST}
      port: 5432
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

See the full `sources.yaml` for all 6 source configurations.

## Running the Application

Start the services in **three separate terminals**:

```bash
# Terminal 1 — MCP Server (data access layer)
python -m src.mcp_server.server
# Runs on http://localhost:8001

# Terminal 2 — API Server (main application)
python -m src.main
# Runs on http://localhost:8000
# Interactive docs at http://localhost:8000/docs

# Terminal 3 — React Frontend (recommended UI)
cd frontend
npm run dev
# Runs on http://localhost:5173
```

Open **http://localhost:5173** in your browser.

### Alternative: Streamlit UI

```bash
streamlit run streamlit_app.py
# Runs on http://localhost:8501
```

### Frontend Setup (first time only)

```bash
cd frontend
npm install
```

The frontend proxies all `/api` requests to the FastAPI server at `http://localhost:8000` automatically — no extra configuration needed.

### Document Ingestion

Before querying unstructured data (PDFs, docs, CSVs from blob/GCS), ingest them into ChromaDB:

```bash
# Ingest from all enabled storage sources
curl -X POST http://localhost:8000/api/ingest

# Ingest from a specific source
curl -X POST http://localhost:8000/api/ingest/azure_documents

# Check ingestion status
curl http://localhost:8000/api/ingest/status
```

Or click **"Ingest All Documents"** in the sidebar of the React UI.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Send a natural language query through the hybrid RAG pipeline |
| `/api/history/{session_id}` | GET | Retrieve conversation history for a session |
| `/api/history/{session_id}/clear` | DELETE | Clear conversation history |
| `/api/sources` | GET | List all connected data sources and their status |
| `/api/ingest` | POST | Trigger document ingestion from all storage sources |
| `/api/ingest/{source_name}` | POST | Trigger ingestion from a single storage source |
| `/api/ingest/status` | GET | Get ingestion pipeline status |
| `/api/stats` | GET | System statistics (sessions, messages, vector store, sources) |
| `/health` | GET | Health check |
| `/docs` | GET | Interactive API documentation (Swagger UI) |

### Chat Example

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What were the top customers by revenue last quarter?",
    "session_id": "demo"
  }'
```

## How It Works

```
User Query (Natural Language)
         |
   Query Classifier (LLM)
   Classifies as: STRUCTURED / UNSTRUCTURED / HYBRID
         |
   +-----+-----+
   |             |
Structured    Unstructured
Retriever     Retriever
(Text-to-SQL) (ChromaDB Vector Search)
   |             |
   +-----+-----+
         |
   Result Merger
   (Token-budgeted context)
         |
   LLM Response Generation
   (With citations)
```

For **hybrid queries**, both retrievers run in parallel via `asyncio.gather`.

## Adding a New Data Source

1. **Create a connector** in `src/data_sources/`:

```python
from src.data_sources.base import StructuredConnector  # or StorageConnector, DocumentConnector
from src.data_sources.registry import register

@register("mysql")
class MySQLConnector(StructuredConnector):
    async def connect(self):
        # Connection logic
        ...

    async def execute_query(self, query, params=None):
        # Query execution
        ...

    async def get_table_schema(self, table_name):
        # Schema introspection
        ...

    async def list_tables(self):
        # List available tables
        ...
```

2. **Add to `sources.yaml`**:

```yaml
  - name: my_mysql
    type: mysql
    enabled: true
    connection:
      host: ${MYSQL_HOST}
      database: ${MYSQL_DB}
      user: ${MYSQL_USER}
      password: ${MYSQL_PASSWORD}
```

3. **Set environment variables** in `.env` and restart.

The system auto-discovers the new source — no changes to query logic, MCP tools, or the UI.

## Project Structure

```
src/
├── agents/
│   ├── orchestrator.py          # Hybrid RAG orchestrator
│   ├── query_classifier.py      # LLM-based query routing
│   ├── structured_retriever.py  # Text-to-SQL retrieval
│   ├── unstructured_retriever.py# Vector search retrieval
│   ├── result_merger.py         # Token-budgeted context merging
│   └── data_catalog.py          # Dynamic source cataloging
├── data_sources/
│   ├── base.py                  # Abstract base classes (Structured/Storage/Document)
│   ├── registry.py              # Plugin registry with @register decorator
│   ├── postgres_connector.py    # PostgreSQL connector
│   ├── bigquery_connector.py    # BigQuery connector
│   ├── azure_sql_connector.py   # Azure SQL connector
│   ├── azure_blob_connector.py  # Azure Blob Storage connector
│   ├── cosmos_connector.py      # Azure Cosmos DB connector
│   └── gcs_connector.py         # Google Cloud Storage connector
├── document_processing/
│   ├── parsers.py               # File parsers (PDF, DOCX, CSV, Excel, JSON, TXT)
│   ├── chunker.py               # Token-based text chunking
│   ├── embedder.py              # OpenAI embedding generation
│   ├── vector_store.py          # ChromaDB vector store
│   └── ingestion.py             # End-to-end ingestion pipeline
├── mcp_server/
│   ├── server.py                # MCP server with dynamic tool registration
│   ├── tools.py                 # Tool definitions per source
│   └── handlers.py              # Request handlers with SQL safety guards
├── models/
│   └── schemas.py               # Pydantic models (ChatRequest, ChatResponse, etc.)
├── config.py                    # Settings and YAML config loader
└── main.py                      # FastAPI application entry point

frontend/
├── src/
│   ├── components/              # React components (Sidebar, ChatPanel, etc.)
│   ├── api/client.ts            # API fetch wrappers
│   ├── types/index.ts           # TypeScript types
│   ├── App.tsx                  # Root layout
│   └── index.css                # Fluent Design styles
├── vite.config.ts               # Dev server + /api proxy to :8000
└── package.json

streamlit_app.py                 # Alternative Streamlit UI
sources.yaml                     # Data source configuration
pyproject.toml                   # Python dependencies
requirements.txt                 # pip-installable dependencies
```

## Running Tests

```bash
python -m pytest tests/
```

Tests cover: connector registry, structured/storage connectors, document parsers, text chunking, vector store operations, and result merging.

## Technology Stack

| Component | Technology |
|-----------|------------|
| LLM | OpenAI GPT-4 Turbo |
| Web Framework | FastAPI + Uvicorn |
| UI | React + Vite + Tailwind CSS (Fluent Design) |
| Alt UI | Streamlit |
| Vector Store | ChromaDB |
| Embeddings | OpenAI text-embedding-3-small + tiktoken |
| Databases | PostgreSQL, BigQuery, Azure SQL |
| Cloud Storage | Azure Blob Storage, Google Cloud Storage |
| Document Store | Azure Cosmos DB |
| Document Parsing | pypdf, python-docx, openpyxl |
| Data Validation | Pydantic v2 |
| Configuration | YAML + python-dotenv |
| Testing | pytest + pytest-asyncio |

## License

MIT License
