import { getSources } from "@/lib/queries";
import { SourcesTable } from "./SourcesTable";

export const dynamic = "force-dynamic";

export default function SourcesPage() {
  const sources = getSources();

  return (
    <main>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Sources</h1>
        <p className="text-sm text-gray-500 mt-1">
          Manage your configured news sources ({sources.length} total)
        </p>
      </div>

      <SourcesTable sources={sources} />
    </main>
  );
}
