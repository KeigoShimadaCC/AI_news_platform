import { getLatestDigest } from "@/lib/queries";
import { DigestTabs } from "./DigestTabs";

export const dynamic = "force-dynamic";
export const revalidate = 300; // 5 min ISR

export default function HomePage() {
  const digest = getLatestDigest();

  return (
    <main>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Daily Digest</h1>
        <p className="text-sm text-gray-500 mt-1">
          {digest.date} &middot; {digest.news.length + digest.tips.length + digest.papers.length}{" "}
          items curated
        </p>
      </div>

      <DigestTabs digest={digest} />
    </main>
  );
}
