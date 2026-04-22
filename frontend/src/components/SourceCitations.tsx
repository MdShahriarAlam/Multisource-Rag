import { useState } from "react";
import { ChevronDown, ChevronRight, Clock, Database, FileText, Hash } from "lucide-react";
import type { DataSource, DocumentSource } from "../types";

function Section({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-fluent-lg border border-[rgba(255,255,255,0.08)] overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3.5 py-2 text-[11.5px] text-[rgba(255,255,255,0.45)] hover:text-[rgba(255,255,255,0.75)] hover:bg-[rgba(255,255,255,0.04)] transition-colors"
      >
        <span className="text-[rgba(255,255,255,0.3)]">{icon}</span>
        <span className="flex-1 text-left font-medium">{title}</span>
        <span className="text-[rgba(255,255,255,0.28)]">
          {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </span>
      </button>
      {open && (
        <div className="border-t border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.18)] divide-y divide-[rgba(255,255,255,0.05)]">
          {children}
        </div>
      )}
    </div>
  );
}

export default function SourceCitations({ dbSources, docSources }: { dbSources: DataSource[]; docSources: DocumentSource[] }) {
  if (!dbSources.length && !docSources.length) return null;

  return (
    <div className="mt-3.5 space-y-2">
      {dbSources.length > 0 && (
        <Section
          title={`${dbSources.length} database source${dbSources.length > 1 ? "s" : ""}`}
          icon={<Database size={12} />}
        >
          {dbSources.map((s, i) => (
            <div key={i} className="px-3.5 py-3 space-y-2.5">
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-[11.5px] font-semibold text-[#60cdff]">{s.source}</span>
                <span className="flex items-center gap-1 text-[11px] text-[rgba(255,255,255,0.38)]">
                  <Hash size={9} /> {s.records} rows
                </span>
                <span className="flex items-center gap-1 text-[11px] text-[rgba(255,255,255,0.38)]">
                  <Clock size={9} /> {s.execution_time_ms.toFixed(0)} ms
                </span>
              </div>
              <pre className="text-[11px] font-mono bg-[rgba(0,0,0,0.35)] border border-[rgba(255,255,255,0.07)] rounded-fluent-md p-3 overflow-x-auto text-[rgba(255,255,255,0.65)] leading-relaxed">
                {s.query}
              </pre>
            </div>
          ))}
        </Section>
      )}

      {docSources.length > 0 && (
        <Section
          title={`${docSources.length} document source${docSources.length > 1 ? "s" : ""}`}
          icon={<FileText size={12} />}
        >
          {docSources.map((d, i) => (
            <div key={i} className="px-3.5 py-3 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[11.5px] font-medium text-[#60cdff] truncate">{d.file_path}</span>
                <span className="text-[10.5px] text-[rgba(255,255,255,0.38)] flex-shrink-0">
                  {(d.relevance_score * 100).toFixed(0)}%
                </span>
              </div>
              {/* Progress bar */}
              <div className="h-1 rounded-full bg-[rgba(255,255,255,0.06)] overflow-hidden">
                <div
                  className="h-1 rounded-full bg-gradient-to-r from-[#60cdff] to-[#a78bfa] transition-all"
                  style={{ width: `${(d.relevance_score * 100).toFixed(0)}%` }}
                />
              </div>
              <p className="text-[11.5px] text-[rgba(255,255,255,0.45)] leading-relaxed border-l-2 border-[rgba(96,205,255,0.2)] pl-3">
                {d.chunk_text.slice(0, 260)}{d.chunk_text.length > 260 ? "…" : ""}
              </p>
            </div>
          ))}
        </Section>
      )}
    </div>
  );
}
