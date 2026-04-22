"""Streamlit UI for Multi-Source RAG Agent."""
import streamlit as st
import requests

# Configuration
BASE_URL = "http://localhost:8000"
API_URL = f"{BASE_URL}/api/chat"

st.set_page_config(
    page_title="Multi-Source RAG Agent",
    page_icon="",
    layout="wide",
)

st.title("Multi-Source RAG Agent")
st.markdown("Ask questions in natural language - the system finds data across all your sources.")

# Session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = "streamlit_session"

# Sidebar
with st.sidebar:
    st.header("Connected Sources")

    try:
        sources_resp = requests.get(f"{BASE_URL}/api/sources", timeout=5)
        if sources_resp.status_code == 200:
            sources = sources_resp.json().get("sources", [])
            if sources:
                for s in sources:
                    badge = {"postgresql": "SQL", "bigquery": "SQL", "azure_sql": "SQL",
                             "azure_blob": "Storage", "gcs": "Storage",
                             "azure_cosmos": "NoSQL"}.get(s["type"], s["type"])
                    st.markdown(f"**{s['name']}** `{badge}`")
            else:
                st.info("No sources connected")
        else:
            st.warning("Could not reach API")
    except Exception:
        st.warning("API not available. Start the server first.")

    st.markdown("---")

    # Ingestion controls
    st.header("Document Ingestion")

    if st.button("Ingest All Documents"):
        with st.spinner("Ingesting documents..."):
            try:
                resp = requests.post(f"{BASE_URL}/api/ingest", timeout=120)
                if resp.status_code == 200:
                    result = resp.json()
                    st.success("Ingestion complete!")
                    for source_name, stats in result.get("results", {}).items():
                        files = stats.get("files_processed", 0)
                        chunks = stats.get("chunks_created", 0)
                        st.caption(f"{source_name}: {files} files, {chunks} chunks")
                else:
                    st.error(f"Ingestion failed: {resp.status_code}")
            except Exception as e:
                st.error(f"Error: {e}")

    # Ingestion status
    try:
        status_resp = requests.get(f"{BASE_URL}/api/ingest/status", timeout=5)
        if status_resp.status_code == 200:
            status = status_resp.json()
            total = status.get("vector_store", {}).get("total_chunks", 0)
            if total > 0:
                st.caption(f"Indexed: {total} document chunks")
    except Exception:
        pass

    st.markdown("---")
    st.header("How to Use")
    st.markdown("""
    **Database queries:**
    - "Show me all customers"
    - "Top 5 customers by revenue"

    **Document search:**
    - "What does the Q3 report say?"
    - "Summarize the compliance policy"

    **Hybrid queries:**
    - "Compare sales data with the forecast"
    """)

    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask your question..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = requests.post(
                    API_URL,
                    json={
                        "message": prompt,
                        "session_id": st.session_state.session_id,
                    },
                    timeout=60,
                )

                if response.status_code == 200:
                    result = response.json()

                    st.markdown(result["response"])

                    # Query type indicator
                    query_type = result.get("query_type")
                    if query_type:
                        label = {
                            "structured_only": "Database Query",
                            "unstructured_only": "Document Search",
                            "hybrid": "Hybrid (DB + Docs)",
                        }.get(query_type, query_type)
                        st.caption(f"Retrieval: {label}")

                    # SQL sources
                    if result.get("sources"):
                        with st.expander("Database Sources"):
                            for source in result["sources"]:
                                st.markdown(f"**{source['source']}**")
                                st.code(source["query"], language="sql")
                                st.caption(
                                    f"Records: {source['records']} | "
                                    f"Time: {source['execution_time_ms']:.0f}ms"
                                )

                    # Document sources
                    if result.get("document_sources"):
                        with st.expander("Document Sources"):
                            for doc in result["document_sources"]:
                                score_pct = f"{doc['relevance_score'] * 100:.0f}%"
                                st.markdown(
                                    f"**{doc['file_path']}** ({score_pct} match)\n\n"
                                    f"> {doc['chunk_text']}"
                                )

                    # Reasoning
                    if result.get("reasoning"):
                        with st.expander("Agent Reasoning"):
                            steps = result["reasoning"].split(" -> ")
                            for step in steps:
                                st.text(f"  {step}")

                    st.session_state.messages.append(
                        {"role": "assistant", "content": result["response"]}
                    )
                else:
                    st.error(f"Error: {response.status_code}")

            except Exception as e:
                st.error(f"Error: {e}")
