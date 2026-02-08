import { notFound } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  ExternalLink,
  Clock,
  User,
  Globe,
  Tag,
  Link2,
} from "lucide-react";
import { getItem, getClusterItems, getFavorites } from "@/lib/queries";
import { ScoreBreakdown } from "@/components/ScoreBreakdown";
import { ItemCard } from "@/components/ItemCard";
import { FavoriteButton } from "@/components/FavoriteButton";
import { formatDate, categoryColor, cn, parseSummary } from "@/lib/utils";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function ItemPage({ params }: PageProps) {
  const { id } = await params;
  const item = getItem(decodeURIComponent(id));

  if (!item) {
    notFound();
  }

  const relatedItems = item.cluster_id
    ? getClusterItems(item.cluster_id, item.id)
    : [];
  const favorites = getFavorites();
  const isFavorite = favorites.some((f) => f.item_id === item.id);

  const summaryText =
    (item as { summary?: string }).summary ?? parseSummary(item.summary_json ?? null);
  const fetchedAt = (item as { fetched_at?: string }).fetched_at ?? item.ingested_at;

  return (
    <main>
      <Link
        href="/"
        className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-900 mb-6 transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Digest
      </Link>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          <div className="card p-6">
            <div className="flex items-center gap-2 mb-3">
              <span className={cn("badge", categoryColor(item.category))}>
                {item.category}
              </span>
              <span className="badge bg-gray-100 text-gray-600">
                {item.source_id}
              </span>
              {item.lang && (
                <span className="badge bg-gray-100 text-gray-600">
                  <Globe className="h-3 w-3 mr-1" />
                  {item.lang}
                </span>
              )}
            </div>

            <h1 className="text-xl font-bold text-gray-900 mb-4">{item.title}</h1>

            <div className="flex flex-wrap items-center gap-4 text-sm text-gray-500 mb-6">
              <FavoriteButton itemId={item.id} isFavorite={isFavorite} />
              {item.author && (
                <span className="flex items-center gap-1">
                  <User className="h-4 w-4" />
                  {item.author}
                </span>
              )}
              <span className="flex items-center gap-1">
                <Clock className="h-4 w-4" />
                {formatDate(item.published_at)}
              </span>
              {item.url && (
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-blue-600 hover:text-blue-800 transition-colors"
                >
                  <ExternalLink className="h-4 w-4" />
                  Original
                </a>
              )}
            </div>

            {summaryText && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
                <h2 className="text-sm font-medium text-blue-900 mb-1">
                  AI Summary
                </h2>
                <p className="text-sm text-blue-800">{summaryText}</p>
              </div>
            )}

            {item.content && (
              <div className="prose prose-sm max-w-none text-gray-700 whitespace-pre-wrap">
                {item.content}
              </div>
            )}
          </div>

          {/* Related Items */}
          {relatedItems.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-1.5">
                <Link2 className="h-4 w-4" />
                Related Items (Cluster)
              </h2>
              <div className="space-y-2">
                {relatedItems.map((related) => (
                  <ItemCard key={related.id} item={related} compact />
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          <div className="card p-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">
              Score Breakdown
            </h2>
            <ScoreBreakdown item={item} />
          </div>

          <div className="card p-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">
              Metadata
            </h2>
            <dl className="space-y-2 text-sm">
              <div>
                <dt className="text-gray-500">ID</dt>
                <dd className="font-mono text-xs text-gray-700 break-all">
                  {item.id}
                </dd>
              </div>
              <div>
                <dt className="text-gray-500">Source</dt>
                <dd className="text-gray-700">{item.source_id}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Fetched</dt>
                <dd className="text-gray-700">{fetchedAt ? formatDate(fetchedAt) : "—"}</dd>
              </div>
              {item.cluster_id && (
                <div>
                  <dt className="text-gray-500 flex items-center gap-1">
                    <Tag className="h-3 w-3" />
                    Cluster
                  </dt>
                  <dd className="font-mono text-xs text-gray-700 break-all">
                    {item.cluster_id}
                  </dd>
                </div>
              )}
            </dl>
          </div>
        </div>
      </div>
    </main>
  );
}
