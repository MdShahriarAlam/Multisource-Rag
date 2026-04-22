interface Props { type: string }

const typeMap: Record<string, { label: string; color: string }> = {
  postgresql:   { label: "SQL",     color: "text-[#60cdff] bg-[rgba(96,205,255,0.08)] border-[rgba(96,205,255,0.18)]" },
  mysql:        { label: "SQL",     color: "text-[#60cdff] bg-[rgba(96,205,255,0.08)] border-[rgba(96,205,255,0.18)]" },
  bigquery:     { label: "SQL",     color: "text-[#60cdff] bg-[rgba(96,205,255,0.08)] border-[rgba(96,205,255,0.18)]" },
  azure_sql:    { label: "SQL",     color: "text-[#60cdff] bg-[rgba(96,205,255,0.08)] border-[rgba(96,205,255,0.18)]" },
  azure_blob:   { label: "Storage", color: "text-[#a78bfa] bg-[rgba(167,139,250,0.08)] border-[rgba(167,139,250,0.18)]" },
  gcs:          { label: "Storage", color: "text-[#a78bfa] bg-[rgba(167,139,250,0.08)] border-[rgba(167,139,250,0.18)]" },
  azure_cosmos: { label: "NoSQL",   color: "text-[#4ade80] bg-[rgba(74,222,128,0.08)] border-[rgba(74,222,128,0.18)]" },
};

export default function SourceBadge({ type }: Props) {
  const meta = typeMap[type] ?? {
    label: type,
    color: "text-[rgba(255,255,255,0.45)] bg-[rgba(255,255,255,0.05)] border-[rgba(255,255,255,0.1)]",
  };
  return (
    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full border tracking-wide flex-shrink-0 ${meta.color}`}>
      {meta.label}
    </span>
  );
}
