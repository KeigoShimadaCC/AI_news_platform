import { getSources } from "@/lib/queries";
import { SettingsForm } from "./SettingsForm";

export const dynamic = "force-dynamic";

export default function SettingsPage() {
  const sources = getSources();

  return (
    <main>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-sm text-gray-500 mt-1">
          Keyword filters and per-source preferences
        </p>
      </div>

      <SettingsForm sources={sources} />
    </main>
  );
}
