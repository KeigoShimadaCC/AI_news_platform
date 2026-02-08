import Link from "next/link";
import { ExternalLink, Clock, BarChart3 } from "lucide-react";
import type { ItemWithMetrics } from "@/lib/types";
import { cn, truncate, timeAgo, scoreColor, categoryColor } from "@/lib/utils";

interface ItemCardProps {
  item: ItemWithMetrics;
  compact?: boolean;
}

export function ItemCard({ item, compact = false }: ItemCardProps) {
  const scorePercent = item.score != null ? Math.round(item.score * 100) : null;

  return (
    <article className="card p-4 hover:border-gray-300 transition-colors">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <span className={cn("badge", categoryColor(item.category))}>
              {item.category}
            </span>
            <span className="text-xs text-gray-400">{item.source_id}</span>
            {item.language && item.language !== "en" && (
              <span className="badge bg-gray-100 text-gray-600">{item.language}</span>
            )}
          </div>

          <Link
            href={`/item/${encodeURIComponent(item.id)}`}
            className="block group"
          >
            <h3 className="text-sm font-semibold text-gray-900 group-hover:text-blue-600 transition-colors line-clamp-2">
              {item.title}
            </h3>
          </Link>

          {!compact && item.summary_json && (
            <p className="mt-1.5 text-sm text-gray-500 line-clamp-2">
              {parseSummary(item.summary_json)}
            </p>
          )}
          {!compact && !item.summary_json && item.content && (
            <p className="mt-1.5 text-sm text-gray-500 line-clamp-2">
              {truncate(item.content, 200)}
            </p>
          )}

          <div className="mt-2 flex items-center gap-3 text-xs text-gray-400">
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {timeAgo(item.published_at)}
            </span>
            {item.author && (
              <span className="truncate max-w-[150px]">{item.author}</span>
            )}
            {scorePercent != null && (
              <span className={cn("flex items-center gap-1 font-medium", scoreColor(item.score))}>
                <BarChart3 className="h-3 w-3" />
                {scorePercent}
              </span>
            )}
          </div>
        </div>

        {item.url && (
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-shrink-0 p-1.5 text-gray-400 hover:text-blue-600 transition-colors"
            title="Open original"
          >
            <ExternalLink className="h-4 w-4" />
          </a>
        )}
      </div>
    </article>
  );
}
