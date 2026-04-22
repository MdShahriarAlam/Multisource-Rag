import { Sparkles } from "lucide-react";

export default function ThinkingIndicator() {
  return (
    <div className="flex items-start gap-3 animate-slideUp">
      {/* Avatar */}
      <div className="relative flex-shrink-0 mt-0.5">
        <div className="absolute inset-0 rounded-fluent-md bg-gradient-to-br from-[#60cdff] to-[#a78bfa] opacity-20 blur-[4px]" />
        <div className="relative w-7 h-7 rounded-fluent-md bg-gradient-to-br from-[rgba(96,205,255,0.12)] to-[rgba(167,139,250,0.08)] border border-[rgba(96,205,255,0.22)] flex items-center justify-center">
          <Sparkles size={12} className="text-[#60cdff] animate-pulse" />
        </div>
      </div>

      <div className="bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.08)] rounded-fluent-xl rounded-tl-fluent px-5 py-3.5 shadow-fluent-sm">
        <div className="flex items-center gap-1.5">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="w-1.5 h-1.5 rounded-full bg-[rgba(96,205,255,0.5)] animate-dot"
              style={{ animationDelay: `${i * 0.24}s` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
