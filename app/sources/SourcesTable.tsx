"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import {
  Radio,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Clock,
  Hash,
  Power,
  PowerOff,
} from "lucide-react";
import type { Source } from "@/lib/types";
import { cn, timeAgo } from "@/lib/utils";
import { EmptyState } from "@/components/EmptyState";

interface SourcesTableProps {
  sources: Source[];
}

export function SourcesTable({ sources }: SourcesTableProps) {
  const router = useRouter();

  const ingestMutation = useMutation({
    mutationFn: async (sourceId: string) => {
      const res = await fetch("/api/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: sourceId }),
      });
      if (!res.ok) throw new Error("Ingest failed");
      return res.json();
    },
    onSuccess: () => router.refresh(),
  });

  const setEnabledMutation = useMutation({
    mutationFn: async ({ id, enabled }: { id: string; enabled: boolean }) => {
      const res = await fetch("/api/sources", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, enabled }),
      });
      if (!res.ok) throw new Error("Failed to update source");
      return res.json();
    },
    onSuccess: () => router.refresh(),
  });

  if (sources.length === 0) {
    return (
      <EmptyState
        title="No sources configured"
        description="Sources are defined in config.yaml. Run an initial ingest to fetch content from all enabled sources."
        action={
          <button
            onClick={() => ingestMutation.mutate("")}
            disabled={ingestMutation.isPending}
            className="btn-primary"
          >
            {ingestMutation.isPending ? (
              <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Radio className="h-4 w-4 mr-2" />
            )}
            Run Initial Ingest
          </button>
        }
      />
    );
  }

  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50">
              <th className="text-left px-4 py-3 font-medium text-gray-600">Source</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Type</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Category</th>
              <th className="text-right px-4 py-3 font-medium text-gray-600">Authority</th>
              <th className="text-right px-4 py-3 font-medium text-gray-600">Items</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Last Fetch</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
              <th className="text-right px-4 py-3 font-medium text-gray-600">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {sources.map((source) => (
              <tr key={source.id} className="hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3">
                  <div className="font-medium text-gray-900">{source.id}</div>
                  <div className="text-xs text-gray-400 truncate max-w-[200px]">
                    {source.url}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className="badge bg-gray-100 text-gray-700">{source.type}</span>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={cn(
                      "badge",
                      source.category === "news"
                        ? "bg-blue-100 text-blue-700"
                        : source.category === "tips"
                          ? "bg-green-100 text-green-700"
                          : "bg-purple-100 text-purple-700"
                    )}
                  >
                    {source.category}
                  </span>
                </td>
                <td className="px-4 py-3 text-right font-mono text-xs">
                  {source.authority.toFixed(2)}
                </td>
                <td className="px-4 py-3 text-right">
                  <span className="flex items-center justify-end gap-1 text-gray-600">
                    <Hash className="h-3 w-3" />
                    {source.item_count}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {source.last_fetch ? (
                    <span className="flex items-center gap-1 text-gray-500 text-xs">
                      <Clock className="h-3 w-3" />
                      {timeAgo(source.last_fetch)}
                    </span>
                  ) : (
                    <span className="text-xs text-gray-400">Never</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {source.last_error ? (
                    <span className="flex items-center gap-1 text-red-600 text-xs" title={source.last_error}>
                      <XCircle className="h-3.5 w-3.5" />
                      Error
                    </span>
                  ) : source.enabled !== false ? (
                    <span className="flex items-center gap-1 text-green-600 text-xs">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Active
                    </span>
                  ) : (
                    <span className="text-xs text-gray-400">Disabled</span>
                  )}
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-1">
                    <button
                      onClick={() =>
                        setEnabledMutation.mutate({
                          id: source.id,
                          enabled: !(source.enabled === true || source.enabled === 1),
                        })
                      }
                      disabled={setEnabledMutation.isPending}
                      className="btn-ghost text-xs p-1.5"
                      title={
                        source.enabled === false
                          ? `Enable ${source.id}`
                          : `Disable ${source.id} (excluded from next ingest)`
                      }
                    >
                      {source.enabled === false ? (
                        <Power className="h-3.5 w-3.5 text-gray-400" />
                      ) : (
                        <PowerOff className="h-3.5 w-3.5 text-green-600" />
                      )}
                    </button>
                    <button
                      onClick={() => ingestMutation.mutate(source.id)}
                      disabled={ingestMutation.isPending}
                      className="btn-ghost text-xs p-1.5"
                      title={`Refresh ${source.id}`}
                    >
                      <RefreshCw
                        className={cn(
                          "h-3.5 w-3.5",
                          ingestMutation.isPending &&
                            ingestMutation.variables === source.id &&
                            "animate-spin"
                        )}
                      />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
