"use client";

import type { SearchFilters } from "@/lib/types";

interface FiltersProps {
  filters: SearchFilters;
  onChange: (filters: SearchFilters) => void;
}

export function Filters({ filters, onChange }: FiltersProps) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <select
        value={filters.category || ""}
        onChange={(e) => onChange({ ...filters, category: e.target.value || undefined })}
        className="input w-auto"
      >
        <option value="">All Categories</option>
        <option value="news">News</option>
        <option value="tips">Tips</option>
        <option value="paper">Papers</option>
      </select>

      <select
        value={filters.lang || ""}
        onChange={(e) => onChange({ ...filters, lang: e.target.value || undefined })}
        className="input w-auto"
      >
        <option value="">All Languages</option>
        <option value="en">English</option>
        <option value="ja">Japanese</option>
      </select>

      <select
        value={filters.sortBy || "score"}
        onChange={(e) =>
          onChange({
            ...filters,
            sortBy: (e.target.value as SearchFilters["sortBy"]) || undefined,
          })
        }
        className="input w-auto"
      >
        <option value="score">Sort by Score</option>
        <option value="date">Sort by Date</option>
        <option value="relevance">Sort by Relevance</option>
      </select>

      <input
        type="date"
        value={filters.dateFrom || ""}
        onChange={(e) => onChange({ ...filters, dateFrom: e.target.value || undefined })}
        className="input w-auto"
        placeholder="From date"
      />

      <input
        type="date"
        value={filters.dateTo || ""}
        onChange={(e) => onChange({ ...filters, dateTo: e.target.value || undefined })}
        className="input w-auto"
        placeholder="To date"
      />

      {Object.values(filters).some(Boolean) && (
        <button
          onClick={() => onChange({})}
          className="btn-ghost text-xs text-gray-500"
        >
          Clear filters
        </button>
      )}
    </div>
  );
}
