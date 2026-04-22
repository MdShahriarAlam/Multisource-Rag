export interface DataSource {
  source: string;
  query: string;
  records: number;
  execution_time_ms: number;
}

export interface DocumentSource {
  source: string;
  file_path: string;
  chunk_text: string;
  relevance_score: number;
}

export type QueryType = "structured_only" | "unstructured_only" | "hybrid";

export interface ChatResponse {
  response: string;
  sources: DataSource[];
  document_sources: DocumentSource[];
  reasoning: string;
  query_type: QueryType | null;
  session_id: string;
  timestamp: string;
}

export interface ConnectedSource {
  name: string;
  type: string;
  enabled: boolean;
}

export interface IngestionStatus {
  vector_store: Record<string, number>;
  sources: Record<string, unknown>;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  chatResponse?: ChatResponse;
}
