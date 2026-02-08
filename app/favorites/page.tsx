"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Star, ExternalLink, Loader2 } from "lucide-react";
import type { Favorite } from "@/lib/types";
import { cn, timeAgo, categoryColor, parseSummary } from "@/lib/utils";

export default function FavoritesPage() {
  const [summarizing, setSummarizing] = useState(false);
  const queryClient = useQueryClient();

  const { data: favorites, isLoading } = useQuery<Favorite[]>({
    queryKey: ["favorites"],
    queryFn: async () => {
      const res = await fetch("/api/favorites");
      if (!res.ok) return [];
      return res.json();
    },
  });

  const handleRemove = async (itemId: string) => {
    await fetch(`/api/favorites?item_id=${encodeURIComponent(itemId)}`, {
      method: "DELETE",
    });
    await queryClient.invalidateQueries({ queryKey: ["favorites"] });
  };

  const handleSummarize = async () => {
    setSummarizing(true);
    try {
      const res = await fetch("/api/favorites/summarize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const data = await res.json();
      if (data.success) {
        await queryClient.invalidateQueries({ queryKey: ["favorites"] });
      }
    } finally {
      setSummarizing(false);
    }
  };

  const hasMissingSummaries = (favorites ?? []).some((f) => !f.summary?.trim());

  return (
    <main>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Favorites</h1>
          <p className="text-sm text-gray-500 mt-1">
            Saved items with optional AI summaries (uses config LLM: local / OpenAI / mock)
          </p>
        </div>
        {hasMissingSummaries && (
          <button
            type="button"
            onClick={handleSummarize}
            disabled={summarizing}
            className="btn-primary flex items-center gap-2"
          >
            {summarizing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Star className="h-4 w-4" />
            )}
            Generate summaries
          </button>
        )}
      </div>

      {isLoading ? (
        <p className="text-gray-500">Loading favorites…</p>
      ) : !favorites?.length ? (
        <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-8 text-center">
          <Star className="mx-auto h-10 w-10 text-gray-400" />
          <p className="mt-2 font-medium text-gray-700">No favorites yet</p>
          <p className="text-sm text-gray-500 mt-1">
            Use the star on search or digest items to save them here.
          </p>
          <Link href="/search" className="mt-4 inline-block text-blue-600 hover:underline">
            Go to Search →
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {favorites.map((fav) => (
            <article
              key={fav.item_id}
              className="card p-4 hover:border-gray-300 transition-colors"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1.5">
                    <span
                      className={cn("badge", categoryColor(fav.item?.category ?? "news"))}
                    >
                      {fav.item?.category ?? "—"}
                    </span>
                    <span className="text-xs text-gray-400">
                      {fav.item?.source_id ?? fav.item_id}
                    </span>
                    <span className="text-xs text-gray-400">
                      {fav.item?.published_at && timeAgo(fav.item.published_at)}
                    </span>
                  </div>
                  <Link
                    href={`/item/${encodeURIComponent(fav.item_id)}`}
                    className="block group"
                  >
                    <h3 className="text-sm font-semibold text-gray-900 group-hover:text-blue-600 line-clamp-2">
                      {fav.item?.title ?? fav.item_id}
                    </h3>
                  </Link>
                  {fav.summary ? (
                    <p className="mt-1.5 text-sm text-gray-600 line-clamp-3">
                      {fav.summary}
                    </p>
                  ) : (
                    fav.item?.summary_json && (
                      <p className="mt-1.5 text-sm text-gray-500 line-clamp-2">
                        {parseSummary(fav.item.summary_json)}
                      </p>
                    )
                  )}
                  {!fav.summary && (
                    <p className="mt-1 text-xs text-amber-600">
                      No summary yet — click &quot;Generate summaries&quot; above.
                    </p>
                  )}
                </div>
                <div className="flex flex-shrink-0 items-center gap-1">
                  <button
                    type="button"
                    onClick={() => handleRemove(fav.item_id)}
                    className="p-1.5 text-gray-400 hover:text-red-500 rounded"
                    title="Remove from favorites"
                  >
                    <Star className="h-4 w-4" fill="currentColor" />
                  </button>
                  {fav.item?.url && (
                    <a
                      href={fav.item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-1.5 text-gray-400 hover:text-blue-600"
                      title="Open original"
                    >
                      <ExternalLink className="h-4 w-4" />
                    </a>
                  )}
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </main>
  );
}
