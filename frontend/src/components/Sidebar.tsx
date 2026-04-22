import { useEffect, useRef, useState } from "react";
import { RefreshCw, Sparkles, Trash2, Upload, FileText, X, DatabaseZap } from "lucide-react";
import type { ConnectedSource, IngestionStatus } from "../types";
import { getSources, ingestAll, getIngestionStatus, uploadFile, listUploadedFiles, deleteUploadedFile, clearVectorStore } from "../api/client";
import SourceBadge from "./SourceBadge";

interface Props {
  sessionId: string;
  onClearChat: () => void;
}

function useReveal(ref: React.RefObject<HTMLElement | null>) {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const move = (e: MouseEvent) => {
      const r = el.getBoundingClientRect();
      el.style.setProperty("--x", `${e.clientX - r.left}px`);
      el.style.setProperty("--y", `${e.clientY - r.top}px`);
    };
    el.addEventListener("mousemove", move);
    return () => el.removeEventListener("mousemove", move);
  }, [ref]);
}

function RevealButton({ children, onClick, disabled, className }: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  className?: string;
}) {
  const ref = useRef<HTMLButtonElement>(null);
  useReveal(ref as React.RefObject<HTMLElement>);
  return (
    <button ref={ref} onClick={onClick} disabled={disabled} className={`reveal ${className}`}>
      {children}
    </button>
  );
}

export default function Sidebar({ onClearChat }: Props) {
  const [sources, setSources] = useState<ConnectedSource[]>([]);
  const [status, setStatus] = useState<IngestionStatus | null>(null);
  const [ingesting, setIngesting] = useState(false);
  const [ingestMsg, setIngestMsg] = useState("");
  const [uploadedFiles, setUploadedFiles] = useState<Array<{ name: string; size: number }>>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const [clearing, setClearing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getSources().then(setSources);
    getIngestionStatus().then(setStatus);
    listUploadedFiles().then(setUploadedFiles);
  }, []);

  async function handleIngest() {
    setIngesting(true);
    setIngestMsg("");
    try {
      const res = await ingestAll();
      const results = res.results as Record<string, { chunks_created: number }> | undefined;
      const total = results
        ? Object.values(results).reduce((s, r) => s + (r.chunks_created ?? 0), 0)
        : 0;
      setIngestMsg(`${total} chunks indexed`);
      getIngestionStatus().then(setStatus);
    } catch (e: unknown) {
      setIngestMsg((e as Error).message ?? "Error");
    } finally {
      setIngesting(false);
    }
  }

  async function handleClearVectors() {
    if (!window.confirm("This will permanently delete all vector embeddings AND all uploaded files. Continue?")) return;
    setClearing(true);
    try {
      await clearVectorStore();
      setUploadMsg("Vector store cleared");
      setUploadedFiles([]);
      getIngestionStatus().then(setStatus);
    } catch (err: unknown) {
      setUploadMsg((err as Error).message ?? "Clear failed");
    } finally {
      setClearing(false);
    }
  }

  async function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";
    setUploading(true);
    setUploadMsg("");
    try {
      const res = await uploadFile(file);
      setUploadMsg(`${res.chunks_created} chunks indexed`);
      listUploadedFiles().then(setUploadedFiles);
      getIngestionStatus().then(setStatus);
    } catch (err: unknown) {
      setUploadMsg((err as Error).message ?? "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleDeleteFile(name: string) {
    try {
      await deleteUploadedFile(name);
      listUploadedFiles().then(setUploadedFiles);
      getIngestionStatus().then(setStatus);
    } catch {
      // ignore
    }
  }

  const totalChunks = status?.vector_store?.total_chunks ?? 0;

  return (
    <aside className="w-64 flex-shrink-0 h-full flex flex-col acrylic border-r border-[rgba(255,255,255,0.06)]">

      {/* Brand */}
      <div className="px-5 py-5 border-b border-[rgba(255,255,255,0.06)]">
        <div className="flex items-center gap-3">
          {/* Logo */}
          <div className="relative w-8 h-8 flex-shrink-0">
            <div className="absolute inset-0 rounded-fluent-md bg-gradient-to-br from-[#60cdff] to-[#a78bfa] opacity-20 blur-[6px]" />
            <div className="relative w-8 h-8 rounded-fluent-md bg-gradient-to-br from-[rgba(96,205,255,0.15)] to-[rgba(167,139,250,0.1)] border border-[rgba(96,205,255,0.25)] flex items-center justify-center">
              <Sparkles size={14} className="text-[#60cdff]" />
            </div>
          </div>
          <div>
            <p className="text-[13px] font-semibold text-white leading-tight tracking-tight">RAG Agent</p>
            <p className="text-[10px] text-[rgba(255,255,255,0.35)] mt-0.5 tracking-wide">Multi-Source</p>
          </div>
        </div>
      </div>

      {/* Sources */}
      <div className="px-4 pt-4 pb-3">
        <p className="text-[10px] font-semibold text-[rgba(255,255,255,0.3)] uppercase tracking-[0.1em] px-1 mb-2.5">
          Data Sources
        </p>
        {sources.length === 0 ? (
          <div className="px-1 py-2 space-y-1.5">
            {[1,2].map(i => (
              <div key={i} className="h-7 rounded-fluent-md shimmer" />
            ))}
          </div>
        ) : (
          <div className="space-y-0.5">
            {sources.map((s) => (
              <div
                key={s.name}
                className="flex items-center gap-2.5 px-2 py-2 rounded-fluent-md hover:bg-[rgba(255,255,255,0.04)] transition-colors group"
              >
                <span className="relative flex-shrink-0">
                  <span className={`w-1.5 h-1.5 rounded-full block ${s.enabled ? "bg-[#4ade80]" : "bg-[rgba(255,255,255,0.18)]"}`} />
                  {s.enabled && (
                    <span className="absolute inset-0 rounded-full bg-[#4ade80] opacity-40 animate-ping" />
                  )}
                </span>
                <span className="flex-1 text-[12px] text-[rgba(255,255,255,0.65)] truncate group-hover:text-[rgba(255,255,255,0.85)] transition-colors">{s.name}</span>
                <SourceBadge type={s.type} />
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="mx-4 border-t border-[rgba(255,255,255,0.06)]" />

      {/* Ingestion */}
      <div className="px-4 py-3">
        <p className="text-[10px] font-semibold text-[rgba(255,255,255,0.3)] uppercase tracking-[0.1em] px-1 mb-2.5">
          Documents
        </p>
        <RevealButton
          onClick={handleIngest}
          disabled={ingesting}
          className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-fluent-md bg-[rgba(255,255,255,0.05)] hover:bg-[rgba(255,255,255,0.08)] border border-[rgba(255,255,255,0.09)] text-[rgba(255,255,255,0.6)] text-[12px] font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <RefreshCw size={11} className={ingesting ? "animate-spin text-[#60cdff]" : ""} />
          {ingesting ? "Ingesting…" : "Ingest All Documents"}
        </RevealButton>
        {ingestMsg && (
          <p className="text-[11px] text-[#4ade80] mt-1.5 text-center font-medium">{ingestMsg}</p>
        )}
        {totalChunks > 0 && (
          <p className="text-[10px] text-[rgba(255,255,255,0.28)] text-center mt-0.5">
            {totalChunks.toLocaleString()} chunks indexed
          </p>
        )}
        <RevealButton
          onClick={handleClearVectors}
          disabled={clearing || ingesting}
          className="w-full flex items-center justify-center gap-2 py-2 px-3 mt-1.5 rounded-fluent-md bg-[rgba(248,113,113,0.06)] hover:bg-[rgba(248,113,113,0.12)] border border-[rgba(248,113,113,0.18)] text-[rgba(248,113,113,0.7)] text-[12px] font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <DatabaseZap size={11} className={clearing ? "animate-pulse" : ""} />
          {clearing ? "Clearing…" : "Clear All Vectors"}
        </RevealButton>
      </div>

      <div className="mx-4 border-t border-[rgba(255,255,255,0.06)]" />

      {/* Upload Files */}
      <div className="px-4 py-3">
        <p className="text-[10px] font-semibold text-[rgba(255,255,255,0.3)] uppercase tracking-[0.1em] px-1 mb-2.5">
          Upload Files
        </p>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt,.csv,.xlsx,.json"
          className="hidden"
          onChange={handleFileSelected}
        />
        <RevealButton
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-fluent-md bg-[rgba(255,255,255,0.05)] hover:bg-[rgba(255,255,255,0.08)] border border-[rgba(255,255,255,0.09)] text-[rgba(255,255,255,0.6)] text-[12px] font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Upload size={11} className={uploading ? "animate-pulse text-[#60cdff]" : ""} />
          {uploading ? "Uploading…" : "Upload PDF / Doc"}
        </RevealButton>
        {uploadMsg && (
          <p className={`text-[11px] mt-1.5 text-center font-medium ${uploadMsg.includes("error") || uploadMsg.includes("Error") ? "text-red-400" : "text-[#4ade80]"}`}>
            {uploadMsg}
          </p>
        )}
        {uploadedFiles.length > 0 && (
          <div className="mt-2 space-y-0.5">
            {uploadedFiles.map((f) => (
              <div
                key={f.name}
                className="flex items-center gap-1.5 px-2 py-1.5 rounded-fluent-md hover:bg-[rgba(255,255,255,0.04)] group"
              >
                <FileText size={10} className="flex-shrink-0 text-[rgba(255,255,255,0.35)]" />
                <span className="flex-1 text-[11px] text-[rgba(255,255,255,0.5)] truncate">{f.name}</span>
                <button
                  onClick={() => handleDeleteFile(f.name)}
                  className="opacity-0 group-hover:opacity-100 transition-opacity text-[rgba(255,255,255,0.3)] hover:text-red-400"
                  title="Remove"
                >
                  <X size={10} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-[rgba(255,255,255,0.06)]">
        <button
          onClick={onClearChat}
          className="w-full flex items-center justify-center gap-1.5 text-[11px] text-[rgba(255,255,255,0.28)] hover:text-[rgba(255,255,255,0.55)] transition-colors py-1.5 rounded-fluent-md hover:bg-[rgba(255,255,255,0.03)]"
        >
          <Trash2 size={10} />
          Clear conversation
        </button>
      </div>
    </aside>
  );
}
