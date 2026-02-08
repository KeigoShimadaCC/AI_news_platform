"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Save, Tag, Globe, Radio } from "lucide-react";
import type { Source } from "@/lib/types";
import type { KeywordSettings } from "@/lib/types";

interface SettingsFormProps {
  sources: Source[];
}

function parseKeywordLine(text: string): string[] {
  return text
    .split(/[\n,]+/)
    .map((k) => k.trim())
    .filter(Boolean);
}

export function SettingsForm({ sources }: SettingsFormProps) {
  const router = useRouter();
  const [settings, setSettings] = useState<KeywordSettings>({
    filterEnabled: false,
    globalKeywords: [],
    sourceKeywords: {},
  });
  const [globalKeywordsText, setGlobalKeywordsText] = useState("");
  const [sourceKeywordsText, setSourceKeywordsText] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    fetch("/api/settings/keywords")
      .then((r) => r.json())
      .then((data) => {
        if (data.filterEnabled !== undefined) {
          const loaded = {
            filterEnabled: data.filterEnabled ?? false,
            globalKeywords: Array.isArray(data.globalKeywords) ? data.globalKeywords : [],
            sourceKeywords:
              data.sourceKeywords && typeof data.sourceKeywords === "object"
                ? data.sourceKeywords
                : {},
          };
          setSettings(loaded);
          setGlobalKeywordsText(loaded.globalKeywords.join("\n"));
          setSourceKeywordsText(
            Object.fromEntries(
              sources.map((s) => [s.id, (loaded.sourceKeywords[s.id] ?? []).join(", ")])
            )
          );
        }
      })
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps -- load once on mount
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    const payload: KeywordSettings = {
      filterEnabled: settings.filterEnabled,
      globalKeywords: [...new Set(parseKeywordLine(globalKeywordsText))],
      sourceKeywords: Object.fromEntries(
        sources.map((src) => [
          src.id,
          [...new Set(parseKeywordLine(sourceKeywordsText[src.id] ?? ""))],
        ])
      ),
    };
    try {
      const res = await fetch("/api/settings/keywords", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        setMessage({ type: "error", text: data.error || "Failed to save" });
        return;
      }
      setMessage({ type: "success", text: "Settings saved. Digest and Search will use your keyword filters." });
      setSettings(payload);
      setGlobalKeywordsText(payload.globalKeywords.join("\n"));
      setSourceKeywordsText(
        Object.fromEntries(
          sources.map((s) => [s.id, (payload.sourceKeywords[s.id] ?? []).join(", ")])
        )
      );
      router.refresh();
    } catch {
      setMessage({ type: "error", text: "Failed to save settings" });
    } finally {
      setSaving(false);
    }
  };

  const setSourceKeywordText = (sourceId: string, text: string) => {
    setSourceKeywordsText((prev) => ({ ...prev, [sourceId]: text }));
  };

  if (loading) {
    return (
      <div className="card p-8 text-center text-gray-500">
        Loading settings…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="card p-6">
        <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900 mb-4">
          <Tag className="h-5 w-5 text-blue-600" />
          Keyword filters
        </h2>
        <p className="text-sm text-gray-600 mb-4">
          When enabled, only articles that contain at least one of your keywords (global or for that source) are shown in Digest and Search.
        </p>

        <label className="flex items-center gap-3 mb-6">
          <input
            type="checkbox"
            checked={settings.filterEnabled}
            onChange={(e) =>
              setSettings((s) => ({ ...s, filterEnabled: e.target.checked }))
            }
            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <span className="text-sm font-medium text-gray-700">
            Only show articles matching my keywords
          </span>
        </label>

        <div className="mb-6">
          <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
            <Globe className="h-4 w-4" />
            Global keywords (any source)
          </label>
          <textarea
            value={globalKeywordsText}
            onChange={(e) => setGlobalKeywordsText(e.target.value)}
            placeholder={"e.g. Claude Code\nGPT-5\nRAG"}
            rows={3}
            className="input font-mono text-sm"
          />
          <p className="text-xs text-gray-500 mt-1">
            One keyword per line, or comma-separated. Spaces inside a keyword are kept (e.g. &quot;Claude Code&quot;). Case-insensitive match in title and content.
          </p>
        </div>

        <div>
          <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
            <Radio className="h-4 w-4" />
            Per-source keywords
          </label>
          <p className="text-xs text-gray-500 mb-3">
            Keywords that apply only to items from that source (e.g. &quot;Clawdbot&quot; for Zenn).
          </p>
          <div className="space-y-3 max-h-[320px] overflow-y-auto pr-2">
            {sources.map((src) => (
              <div
                key={src.id}
                className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 border-b border-gray-100 pb-3 last:border-0"
              >
                <span className="text-sm font-medium text-gray-700 min-w-[140px]">
                  {src.id.replace(/_/g, " ")}
                </span>
                <input
                  type="text"
                  value={sourceKeywordsText[src.id] ?? ""}
                  onChange={(e) => setSourceKeywordText(src.id, e.target.value)}
                  placeholder="e.g. Clawdbot, Claude Code"
                  className="input flex-1 text-sm"
                />
              </div>
            ))}
          </div>
        </div>

        {message && (
          <div
            className={`mt-4 rounded-lg px-4 py-2 text-sm ${
              message.type === "success"
                ? "bg-green-50 text-green-800"
                : "bg-red-50 text-red-800"
            }`}
          >
            {message.text}
          </div>
        )}

        <div className="mt-6 flex justify-end">
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="btn-primary inline-flex items-center gap-2"
          >
            {saving ? (
              <span className="animate-pulse">Saving…</span>
            ) : (
              <>
                <Save className="h-4 w-4" />
                Save settings
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
