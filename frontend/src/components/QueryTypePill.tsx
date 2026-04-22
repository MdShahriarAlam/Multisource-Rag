import { Database, FileText, Layers } from "lucide-react";
import type { QueryType } from "../types";

const map: Record<QueryType, { label: string; icon: React.ReactNode; cls: string }> = {
  structured_only: {
    label: "Database Query",
    icon: <Database size={10} />,
    cls: "text-[#60cdff] bg-[rgba(96,205,255,0.08)] border-[rgba(96,205,255,0.2)]",
  },
  unstructured_only: {
    label: "Document Search",
    icon: <FileText size={10} />,
    cls: "text-[#4ade80] bg-[rgba(74,222,128,0.08)] border-[rgba(74,222,128,0.2)]",
  },
  hybrid: {
    label: "Hybrid",
    icon: <Layers size={10} />,
    cls: "text-[#a78bfa] bg-[rgba(167,139,250,0.08)] border-[rgba(167,139,250,0.2)]",
  },
};

export default function QueryTypePill({ type }: { type: QueryType }) {
  const m = map[type];
  return (
    <span className={`inline-flex items-center gap-1.5 text-[10.5px] font-medium px-2.5 py-1 rounded-full border ${m.cls}`}>
      {m.icon}
      {m.label}
    </span>
  );
}
