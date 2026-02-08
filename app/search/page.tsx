"use client";

import { useState, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { SearchFilters, SearchResult, Source, Favorite } from "@/lib/types";
import { SearchInput } from "@/components/SearchInput";
import { Filters } from "@/components/Filters";
import { ItemCard } from "@/components/ItemCard";
import { Pagination } from "@/components/Pagination";
import { EmptyState } from "@/components/EmptyState";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { debounce } from "@/lib/utils";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [filters, setFilters] = useState<SearchFilters>({});
  const [page, setPage] = useState(1);
  const queryClient = useQueryClient();

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const debouncedSetQuery = useCallback(
    debounce((q: string) => {
      setDebouncedQuery(q);
      setPage(1);
    }, 300),
    []
  );

  const handleQueryChange = (value: string) => {
    setQuery(value);
    debouncedSetQuery(value);
  };

  const handleFilterChange = (newFilters: SearchFilters) => {
    setFilters(newFilters);
    setPage(1);
  };

  const { data: sourcesData } = useQuery<Source[]>({
    queryKey: ["sources"],
    queryFn: async () => {
      const res = await fetch("/api/sources");
      if (!res.ok) return [];
      return res.json();
    },
  });
  const sources = sourcesData ?? [];

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
        ...(method === "POST" ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify({ item_id: itemId }) } : {}),
      });
      if (res.ok) {
        await queryClient.invalidateQueries({ queryKey: ["favorites"] });
      }
    },
    [favoriteIds, queryClient]
  );

  const { data, isLoading } = useQuery<SearchResult>({
    queryKey: ["search", debouncedQuery, filters, page],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (debouncedQuery) params.set("q", debouncedQuery);
      if (filters.category) params.set("category", filters.category);
      if (filters.source) params.set("source", filters.source);
      if (filters.lang) params.set("lang", filters.lang);
      if (filters.dateFrom) params.set("dateFrom", filters.dateFrom);
      if (filters.dateTo) params.set("dateTo", filters.dateTo);
      if (filters.sortBy) params.set("sortBy", filters.sortBy);
      params.set("page", String(page));

      const res = await fetch(`/api/search?${params}`);
      if (!res.ok) throw new Error("Search failed");
      return res.json();
    },
    enabled: true,
  });

  return (
    <main>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Search</h1>
        <p className="text-sm text-gray-500 mt-1">
          Full-text search across all items
        </p>
      </div>

      <div className="space-y-4">
        <SearchInput value={query} onChange={handleQueryChange} />
        <Filters filters={filters} onChange={handleFilterChange} sources={sources.map((s) => ({ id: s.id, label: s.id.replace(/_/g, " ") }))} />

        {data && data.total > 0 && (
          <p className="text-sm text-gray-500">
            {data.total} result{data.total !== 1 ? "s" : ""} found
          </p>
        )}

        {isLoading ? (
          <LoadingSpinner />
        ) : data && data.items.length > 0 ? (
          <>
            <div className="space-y-3">
              {data.items.map((item) => (
                <ItemCard
                  key={item.id}
                  item={item}
                  isFavorite={favoriteIds.has(item.id)}
                  onToggleFavorite={handleToggleFavorite}
                />
              ))}
            </div>
            <Pagination
              page={page}
              totalPages={data.totalPages}
              onPageChange={setPage}
            />
          </>
        ) : debouncedQuery ? (
          <EmptyState
            title="No results found"
            description={`No items match "${debouncedQuery}". Try different keywords or adjust filters.`}
          />
        ) : (
          <EmptyState
            title="Start searching"
            description="Enter a query to search across all articles, papers, and tips."
          />
        )}
      </div>
    </main>
  );
}
