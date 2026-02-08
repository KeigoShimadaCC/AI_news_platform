import type { ItemWithMetrics } from "@/lib/types";

interface ScoreBreakdownProps {
  item: ItemWithMetrics;
}

const factors = [
  { key: "authority" as const, label: "Authority", desc: "Source credibility" },
  { key: "recency" as const, label: "Recency", desc: "How recent" },
  { key: "popularity" as const, label: "Popularity", desc: "Community engagement" },
  { key: "relevance" as const, label: "Relevance", desc: "Topic match" },
  { key: "dup_penalty" as const, label: "Dup Penalty", desc: "Duplication penalty" },
];

export function ScoreBreakdown({ item }: ScoreBreakdownProps) {
  if (item.score == null) {
    return (
      <div className="text-sm text-gray-400 italic">
        Score not yet calculated
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-gray-700">Overall Score</span>
        <span className="text-lg font-bold text-blue-600">
          {Math.round(item.score * 100)}
        </span>
      </div>

      <div className="space-y-2">
        {factors.map(({ key, label, desc }) => {
          const value = item[key];
          if (value == null) return null;
          const pct = Math.round(value * 100);

          return (
            <div key={key}>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-gray-600" title={desc}>
                  {label}
                </span>
                <span className="text-gray-500">{pct}%</span>
              </div>
              <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    key === "dup_penalty" ? "bg-red-400" : "bg-blue-400"
                  }`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
