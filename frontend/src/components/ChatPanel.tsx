import { useEffect, useRef, useState } from "react";
import { ArrowUp, Sparkles, Paperclip, X, FileText } from "lucide-react";
import type { Message } from "../types";
import { sendChat, uploadFile } from "../api/client";
import ChatMessage from "./ChatMessage";
import ThinkingIndicator from "./ThinkingIndicator";

interface Props {
  sessionId: string;
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
}

export default function ChatPanel({ sessionId, messages, setMessages }: Props) {
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const [error, setError] = useState("");
  const [focused, setFocused] = useState(false);
  const [attachment, setAttachment] = useState<{ name: string; uploading: boolean; error?: string } | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, thinking]);


  function handleInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px";
  }

  async function handleFileAttach(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";
    setAttachment({ name: file.name, uploading: true });
    try {
      await uploadFile(file);
      setAttachment({ name: file.name, uploading: false });
    } catch (err: unknown) {
      setAttachment({ name: file.name, uploading: false, error: (err as Error).message });
    }
  }

  async function submit() {
    const text = input.trim();
    if (!text || thinking) return;
    if (attachment?.uploading) return;

    setInput("");
    setError("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";

    const attachedFile = attachment && !attachment.error ? attachment.name : null;
    setAttachment(null);

    const displayText = attachedFile ? `[Attached: ${attachedFile}]\n${text}` : text;

    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: "user", content: displayText, timestamp: new Date() },
    ]);
    setThinking(true);

    const context = attachedFile ? { uploaded_file: attachedFile } : undefined;

    try {
      const res = await sendChat(text, sessionId, context);
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: res.response,
          timestamp: new Date(),
          chatResponse: res,
        },
      ]);
    } catch (e: unknown) {
      setError((e as Error).message ?? "Something went wrong.");
    } finally {
      setThinking(false);
    }
  }

  function handleKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  const canSend = input.trim().length > 0 && !thinking && !attachment?.uploading;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center px-7 py-4 border-b border-[rgba(255,255,255,0.06)] acrylic">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="absolute inset-0 rounded-fluent-md bg-gradient-to-br from-[#60cdff] to-[#a78bfa] opacity-15 blur-[8px]" />
            <div className="relative w-8 h-8 rounded-fluent-md bg-gradient-to-br from-[rgba(96,205,255,0.12)] to-[rgba(167,139,250,0.08)] border border-[rgba(96,205,255,0.2)] flex items-center justify-center">
              <Sparkles size={14} className="text-[#60cdff]" />
            </div>
          </div>
          <div>
            <h1 className="text-[14px] font-semibold text-white leading-tight tracking-tight">
              Multi-Source RAG Agent
            </h1>
            <p className="text-[11px] text-[rgba(255,255,255,0.35)] mt-0.5">
              Natural language queries across all connected data sources
            </p>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
        {messages.length === 0 && !thinking && (
          <div className="flex flex-col items-center justify-center h-full text-center select-none gap-5">
            {/* Hero icon */}
            <div className="relative">
              <div className="absolute inset-0 rounded-[20px] bg-gradient-to-br from-[#60cdff] to-[#a78bfa] opacity-20 blur-[20px]" />
              <div className="relative w-16 h-16 rounded-[20px] bg-gradient-to-br from-[rgba(96,205,255,0.12)] to-[rgba(167,139,250,0.08)] border border-[rgba(96,205,255,0.2)] flex items-center justify-center animate-float">
                <Sparkles size={24} className="text-[#60cdff]" />
              </div>
            </div>
            <div>
              <h2 className="text-[18px] font-semibold text-white mb-2 tracking-tight">
                Ask anything
              </h2>
              <p className="text-[13px] text-[rgba(255,255,255,0.38)] max-w-[300px] leading-relaxed">
                Query your databases and documents in plain English.<br />
                Pick a suggestion from the sidebar to get started.
              </p>
            </div>
            {/* Decorative chips */}
            <div className="flex flex-wrap gap-2 justify-center max-w-[380px] mt-1">
              {["SQL Databases", "Document Search", "Cross-Source Joins", "Natural Language"].map(label => (
                <span
                  key={label}
                  className="text-[11px] text-[rgba(255,255,255,0.35)] px-3 py-1 rounded-full border border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.03)]"
                >
                  {label}
                </span>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <ChatMessage key={msg.id} msg={msg} />
        ))}

        {thinking && <ThinkingIndicator />}

        {error && (
          <div className="flex items-start gap-3 animate-slideUp">
            <div className="w-7 h-7 flex-shrink-0" />
            <div className="text-[12.5px] text-[#f87171] bg-[rgba(248,113,113,0.06)] border border-[rgba(248,113,113,0.18)] rounded-fluent-lg px-4 py-3">
              {error}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-6 pb-5 pt-3 border-t border-[rgba(255,255,255,0.06)] acrylic">
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt,.csv,.xlsx,.json"
          className="hidden"
          onChange={handleFileAttach}
        />

        {/* Attachment pill */}
        {attachment && (
          <div className="flex items-center gap-2 mb-2">
            <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] border ${
              attachment.error
                ? "bg-[rgba(248,113,113,0.08)] border-[rgba(248,113,113,0.25)] text-[#f87171]"
                : attachment.uploading
                ? "bg-[rgba(96,205,255,0.06)] border-[rgba(96,205,255,0.2)] text-[rgba(96,205,255,0.7)]"
                : "bg-[rgba(74,222,128,0.06)] border-[rgba(74,222,128,0.2)] text-[#4ade80]"
            }`}>
              <FileText size={10} />
              <span className="truncate max-w-[200px]">{attachment.name}</span>
              {attachment.uploading && <span className="animate-pulse">uploading…</span>}
              {attachment.error && <span>failed</span>}
              {!attachment.uploading && !attachment.error && <span>ready</span>}
            </div>
            {!attachment.uploading && (
              <button
                onClick={() => setAttachment(null)}
                className="text-[rgba(255,255,255,0.3)] hover:text-[rgba(255,255,255,0.6)] transition-colors"
              >
                <X size={11} />
              </button>
            )}
          </div>
        )}

        <div
          className={`relative flex items-end gap-3 rounded-fluent-xl px-4 py-3 transition-all duration-200 ${
            focused
              ? "bg-[rgba(255,255,255,0.06)] border border-[rgba(96,205,255,0.3)] shadow-glow-accent"
              : "bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.09)]"
          }`}
        >
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={thinking}
            className="flex-shrink-0 text-[rgba(255,255,255,0.3)] hover:text-[rgba(255,255,255,0.65)] transition-colors disabled:opacity-30 mb-0.5"
            title="Attach a PDF or document"
          >
            <Paperclip size={15} />
          </button>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInput}
            onKeyDown={handleKey}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            placeholder="Ask a question about your data…"
            rows={1}
            disabled={thinking}
            className="flex-1 bg-transparent text-[13.5px] text-[rgba(255,255,255,0.88)] placeholder-[rgba(255,255,255,0.28)] resize-none outline-none leading-relaxed disabled:opacity-50"
            style={{ maxHeight: "160px" }}
          />
          <button
            onClick={submit}
            disabled={!canSend}
            className={`flex-shrink-0 w-8 h-8 rounded-fluent-md flex items-center justify-center transition-all duration-150 ${
              canSend
                ? "bg-gradient-to-br from-[#0078d4] to-[#005a9e] hover:from-[#0091f8] hover:to-[#0067bf] text-white shadow-glow-user"
                : "bg-[rgba(255,255,255,0.05)] text-[rgba(255,255,255,0.2)] cursor-not-allowed"
            }`}
          >
            <ArrowUp size={14} />
          </button>
        </div>
        <p className="text-[10px] text-[rgba(255,255,255,0.2)] text-center mt-2.5">
          Enter to send · Shift+Enter for new line · Attach a file with the paperclip
        </p>
      </div>
    </div>
  );
}
