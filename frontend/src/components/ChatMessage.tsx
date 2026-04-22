import { useState } from "react";
import { ChevronDown, ChevronRight, Sparkles } from "lucide-react";
import type { Message } from "../types";
import QueryTypePill from "./QueryTypePill";
import SourceCitations from "./SourceCitations";

// ── Inline formatting ──────────────────────────────────────────────────────
function InlineText({ text }: { text: string }) {
  // Split on **bold**, `code`, keeping delimiters for reconstruction
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**"))
          return <strong key={i} className="font-semibold text-white">{part.slice(2, -2)}</strong>;
        if (part.startsWith("`") && part.endsWith("`"))
          return (
            <code key={i} className="font-mono text-[0.8em] bg-[rgba(96,205,255,0.1)] text-[#60cdff] px-1.5 py-0.5 rounded border border-[rgba(96,205,255,0.15)]">
              {part.slice(1, -1)}
            </code>
          );
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}

// ── Table renderer ─────────────────────────────────────────────────────────
function MarkdownTable({ lines }: { lines: string[] }) {
  const parseRow = (line: string) =>
    line.replace(/^\||\|$/g, "").split("|").map((c) => c.trim());

  const headers = parseRow(lines[0]);
  // lines[1] is the separator row (---|---|---), skip it
  const rows = lines.slice(2).map(parseRow);

  return (
    <div className="overflow-x-auto my-3 rounded-fluent-lg border border-[rgba(255,255,255,0.08)]">
      <table className="w-full text-[12.5px] border-collapse">
        <thead>
          <tr className="bg-[rgba(255,255,255,0.05)]">
            {headers.map((h, i) => (
              <th
                key={i}
                className="px-3 py-2.5 text-left text-[11px] font-semibold text-[rgba(255,255,255,0.5)] uppercase tracking-wider border-b border-[rgba(255,255,255,0.08)] whitespace-nowrap"
              >
                <InlineText text={h} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr
              key={ri}
              className="border-b border-[rgba(255,255,255,0.05)] last:border-0 hover:bg-[rgba(255,255,255,0.025)] transition-colors"
            >
              {row.map((cell, ci) => (
                <td key={ci} className="px-3 py-2 text-[rgba(255,255,255,0.80)]">
                  <InlineText text={cell} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Full markdown renderer ─────────────────────────────────────────────────
function SimpleMarkdown({ text }: { text: string }) {
  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Fenced code block
    if (line.startsWith("```")) {
      const lang = line.slice(3).trim();
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      elements.push(
        <pre key={i} className="bg-[rgba(0,0,0,0.4)] border border-[rgba(255,255,255,0.07)] rounded-fluent-lg px-4 py-3 overflow-x-auto my-2">
          <code className="font-mono text-[0.82em] text-[rgba(255,255,255,0.8)] leading-relaxed">
            {codeLines.join("\n")}
          </code>
        </pre>
      );
      i++;
      continue;
    }

    // Table — collect consecutive table lines
    if (line.startsWith("|")) {
      const tableLines: string[] = [line];
      i++;
      while (i < lines.length && lines[i].startsWith("|")) {
        tableLines.push(lines[i]);
        i++;
      }
      if (tableLines.length >= 3) {
        elements.push(<MarkdownTable key={i} lines={tableLines} />);
      }
      continue;
    }

    // Headings
    if (line.startsWith("### ")) {
      elements.push(<h3 key={i} className="text-[14px] font-semibold text-white mt-3 mb-1">{line.slice(4)}</h3>);
      i++; continue;
    }
    if (line.startsWith("## ")) {
      elements.push(<h2 key={i} className="text-[15px] font-semibold text-white mt-3 mb-1">{line.slice(3)}</h2>);
      i++; continue;
    }
    if (line.startsWith("# ")) {
      elements.push(<h1 key={i} className="text-[16px] font-bold text-white mt-3 mb-1">{line.slice(2)}</h1>);
      i++; continue;
    }

    // Unordered list
    if (line.match(/^[-*] /)) {
      const items: string[] = [];
      while (i < lines.length && lines[i].match(/^[-*] /)) {
        items.push(lines[i].slice(2));
        i++;
      }
      elements.push(
        <ul key={i} className="list-disc pl-5 my-1.5 space-y-0.5">
          {items.map((item, j) => (
            <li key={j} className="text-[rgba(255,255,255,0.82)]"><InlineText text={item} /></li>
          ))}
        </ul>
      );
      continue;
    }

    // Ordered list
    if (line.match(/^\d+\. /)) {
      const items: string[] = [];
      while (i < lines.length && lines[i].match(/^\d+\. /)) {
        items.push(lines[i].replace(/^\d+\. /, ""));
        i++;
      }
      elements.push(
        <ol key={i} className="list-decimal pl-5 my-1.5 space-y-0.5">
          {items.map((item, j) => (
            <li key={j} className="text-[rgba(255,255,255,0.82)]"><InlineText text={item} /></li>
          ))}
        </ol>
      );
      continue;
    }

    // Horizontal rule
    if (line.match(/^---+$/)) {
      elements.push(<hr key={i} className="border-[rgba(255,255,255,0.08)] my-2" />);
      i++; continue;
    }

    // Blank line — spacing
    if (line.trim() === "") {
      i++; continue;
    }

    // Regular paragraph
    elements.push(
      <p key={i} className="text-[rgba(255,255,255,0.85)] leading-relaxed mb-1 last:mb-0">
        <InlineText text={line} />
      </p>
    );
    i++;
  }

  return <div className="text-[13.5px] space-y-0.5">{elements}</div>;
}

function ReasoningSection({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const steps = text.split(" -> ").filter(Boolean);

  return (
    <div className="mt-3 rounded-fluent-lg border border-[rgba(255,255,255,0.07)] overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3.5 py-2 text-[11px] text-[rgba(255,255,255,0.35)] hover:text-[rgba(255,255,255,0.6)] hover:bg-[rgba(255,255,255,0.03)] transition-colors"
      >
        {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
        <span>Show reasoning</span>
        <span className="ml-auto text-[10px] bg-[rgba(255,255,255,0.06)] px-2 py-0.5 rounded-full">
          {steps.length} steps
        </span>
      </button>
      {open && (
        <div className="border-t border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.15)] px-3.5 py-3">
          {/* Timeline */}
          <ol className="relative space-y-0">
            {steps.map((step, i) => (
              <li key={i} className="flex items-start gap-3 pb-3 last:pb-0">
                {/* Timeline line + dot */}
                <div className="flex flex-col items-center flex-shrink-0 mt-0.5">
                  <div className="w-5 h-5 rounded-full border border-[rgba(255,255,255,0.12)] bg-[rgba(255,255,255,0.04)] text-[9px] flex items-center justify-center text-[rgba(255,255,255,0.4)] font-medium">
                    {i + 1}
                  </div>
                  {i < steps.length - 1 && (
                    <div className="w-px flex-1 mt-1 bg-[rgba(255,255,255,0.07)] min-h-[12px]" />
                  )}
                </div>
                <p className="text-[11.5px] text-[rgba(255,255,255,0.50)] leading-relaxed pt-0.5">{step}</p>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

export default function ChatMessage({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";
  const cr = msg.chatResponse;
  const time = msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  if (isUser) {
    return (
      <div className="flex justify-end animate-slideUp">
        <div className="max-w-[72%]">
          <div
            className="relative text-white rounded-fluent-xl rounded-br-fluent px-4 py-3 text-[13.5px] leading-relaxed shadow-glow-user"
            style={{
              background: "linear-gradient(135deg, #1d4ed8 0%, #1e40af 60%, #1d3a8a 100%)",
            }}
          >
            {msg.content}
          </div>
          <p className="text-[10px] text-[rgba(255,255,255,0.25)] text-right mt-1.5 mr-0.5">{time}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3 animate-slideUp">
      {/* Avatar */}
      <div className="relative flex-shrink-0 mt-0.5">
        <div className="absolute inset-0 rounded-fluent-md bg-gradient-to-br from-[#60cdff] to-[#a78bfa] opacity-20 blur-[4px]" />
        <div className="relative w-7 h-7 rounded-fluent-md bg-gradient-to-br from-[rgba(96,205,255,0.12)] to-[rgba(167,139,250,0.08)] border border-[rgba(96,205,255,0.22)] flex items-center justify-center">
          <Sparkles size={12} className="text-[#60cdff]" />
        </div>
      </div>

      <div className="flex-1 min-w-0">
        <div className="bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.08)] rounded-fluent-xl rounded-tl-fluent px-4 py-3.5 shadow-fluent-sm">
          <SimpleMarkdown text={msg.content} />

          {cr?.query_type && (
            <div className="mt-3">
              <QueryTypePill type={cr.query_type} />
            </div>
          )}

          {cr && (
            <SourceCitations
              dbSources={cr.sources ?? []}
              docSources={cr.document_sources ?? []}
            />
          )}

          {cr?.reasoning && <ReasoningSection text={cr.reasoning} />}
        </div>

        <p className="text-[10px] text-[rgba(255,255,255,0.25)] mt-1.5 ml-0.5">{time}</p>
      </div>
    </div>
  );
}
