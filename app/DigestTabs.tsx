"use client";

import { useState, useCallback } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Newspaper, Lightbulb, BookOpen, RefreshCw, Zap, Sparkles } from "lucide-react";
import type { Digest, Favorite } from "@/lib/types";
import { ItemCard } from "@/components/ItemCard";
import { EmptyState } from "@/components/EmptyState";
import { cn } from "@/lib/utils";

interface DigestTabsProps {
  digest: Digest;
}

const tabs = [
  { id: "news" as const, label: "News", icon: Newspaper },
  { id: "tips" as const, label: "Tips", icon: Lightbulb },
  { id: "papers" as const, label: "Papers", icon: BookOpen },
];

export function DigestTabs({ digest }: DigestTabsProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<"news" | "tips" | "papers">("news");

  const { data: favoritesData } = useQuery<Favorite[]>({
    queryKey: ["favorites"],
    queryFn: async () => {
      const res = await fetch("/api/favorites");
      if (!res.ok) return [];
      return res.json();
    },
  });
  const favoriteIds = new Set((favoritesData ?? []).map((f) => f.item_id));

  const handleToggleFavorite = useCallback(
    async (itemId: string) => {
      const isFav = favoriteIds.has(itemId);
      const method = isFav ? "DELETE" : "POST";
      const url = isFav ? `/api/favorites?item_id=${encodeURIComponent(itemId)}` : "/api/favorites";
      const res = await fetch(url, {
        method,
        ...(method === "POST"
          ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify({ item_id: itemId }) }
          : {}),
      });
      if (res.ok) {
        await queryClient.invalidateQueries({ queryKey: ["favorites"] });
      }
    },
    [queryClient]
  );

  const ingestMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch("/api/ingest", { method: "POST", body: JSON.stringify({}) });
      if (!res.ok) throw new Error("Ingest failed");
      return res.json();
    },
  });

  const generateDigestMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch("/api/digest", { method: "POST", body: JSON.stringify({}) });
      if (!res.ok) throw new Error("Generate digest failed");
      return res.json();
    },
    onSuccess: () => {
      router.refresh();
    },
  });

  const items =
    activeTab === "news"
      ? digest.news
      : activeTab === "tips"
        ? digest.tips
        : digest.papers;

  const limits = { news: 20, tips: 20, papers: 10 };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          {tabs.map(({ id, label, icon: Icon }) => {
            const count =
              id === "news"
                ? digest.news.length
                : id === "tips"
                  ? digest.tips.length
                  : digest.papers.length;
            return (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={cn(
                  "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  activeTab === id
                    ? "bg-white text-gray-900 shadow-sm"
                    : "text-gray-500 hover:text-gray-700"
                )}
              >
                <Icon className="h-4 w-4" />
                {label}
                <span
                  className={cn(
                    "text-xs ml-0.5",
                    activeTab === id ? "text-blue-600" : "text-gray-400"
                  )}
                >
                  {count}/{limits[id]}
                </span>
              </button>
            );
          })}
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => generateDigestMutation.mutate()}
            disabled={generateDigestMutation.isPending}
            className="btn-secondary text-xs"
          >
            {generateDigestMutation.isPending ? (
              <RefreshCw className="h-3.5 w-3.5 mr-1.5 animate-spin" />
            ) : (
              <Sparkles className="h-3.5 w-3.5 mr-1.5" />
            )}
            Generate digest
          </button>
          <button
            onClick={() => ingestMutation.mutate()}
            disabled={ingestMutation.isPending}
            className="btn-secondary text-xs"
          >
            {ingestMutation.isPending ? (
              <RefreshCw className="h-3.5 w-3.5 mr-1.5 animate-spin" />
            ) : (
              <Zap className="h-3.5 w-3.5 mr-1.5" />
            )}
            Refresh Sources
          </button>
        </div>
      </div>

      {generateDigestMutation.isSuccess && (
        <div className="mb-4 rounded-lg bg-green-50 border border-green-200 p-3 text-sm text-green-700">
          Digest generated. View updated below.
        </div>
      )}

      {generateDigestMutation.isError && (
        <div className="mb-4 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
          Failed to generate digest. Run ingest first to fetch items.
        </div>
      )}

      {ingestMutation.isSuccess && (
        <div className="mb-4 rounded-lg bg-green-50 border border-green-200 p-3 text-sm text-green-700">
          Sources refreshed successfully. Reload the page to see updates.
        </div>
      )}

      {ingestMutation.isError && (
        <div className="mb-4 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
          Failed to refresh sources. Check that the backend is configured.
        </div>
      )}

      {items.length === 0 ? (
        <EmptyState
          title={`No ${activeTab} items yet`}
          description="Run an ingest to fetch items from configured sources."
        />
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <ItemCard
              key={item.id}
              item={item}
              isFavorite={favoriteIds.has(item.id)}
              onToggleFavorite={handleToggleFavorite}
            />
          ))}
        </div>
      )}
    </div>
  );
}
