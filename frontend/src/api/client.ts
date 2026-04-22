import type { ChatResponse, ConnectedSource, IngestionStatus } from "../types";

const BASE = "/api";

export async function sendChat(
  message: string,
  sessionId: string,
  context?: Record<string, unknown>
): Promise<ChatResponse> {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId, context }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Chat error ${res.status}: ${err}`);
  }
  return res.json();
}

export async function getSources(): Promise<ConnectedSource[]> {
  try {
    const res = await fetch(`${BASE}/sources`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.sources ?? [];
  } catch {
    return [];
  }
}

export async function ingestAll(): Promise<Record<string, unknown>> {
  const res = await fetch(`${BASE}/ingest`, { method: "POST" });
  if (!res.ok) throw new Error(`Ingest error ${res.status}`);
  return res.json();
}

export async function getIngestionStatus(): Promise<IngestionStatus> {
  try {
    const res = await fetch(`${BASE}/ingest/status`);
    if (!res.ok) return { vector_store: {}, sources: {} };
    return res.json();
  } catch {
    return { vector_store: {}, sources: {} };
  }
}

export async function clearHistory(sessionId: string): Promise<void> {
  await fetch(`${BASE}/history/${sessionId}/clear`, { method: "DELETE" });
}

export async function uploadFile(
  file: File
): Promise<{ filename: string; chunks_created: number }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/upload`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Upload error ${res.status}: ${err}`);
  }
  return res.json();
}

export async function listUploadedFiles(): Promise<
  Array<{ name: string; size: number }>
> {
  try {
    const res = await fetch(`${BASE}/upload/files`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.files ?? [];
  } catch {
    return [];
  }
}

export async function clearVectorStore(): Promise<void> {
  const res = await fetch(`${BASE}/vector/clear`, { method: "POST" });
  if (!res.ok) throw new Error(`Clear error ${res.status}`);
}

export async function deleteUploadedFile(filename: string): Promise<void> {
  const res = await fetch(`${BASE}/upload/${encodeURIComponent(filename)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Delete error ${res.status}`);
}
