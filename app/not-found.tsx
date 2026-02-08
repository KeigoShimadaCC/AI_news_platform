import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export default function NotFound() {
  return (
    <main className="flex flex-col items-center justify-center py-24 text-center">
      <h1 className="text-6xl font-bold text-gray-200 mb-4">404</h1>
      <h2 className="text-lg font-medium text-gray-900 mb-2">Page not found</h2>
      <p className="text-sm text-gray-500 mb-6">
        The page you&apos;re looking for doesn&apos;t exist.
      </p>
      <Link href="/" className="btn-primary">
        <ArrowLeft className="h-4 w-4 mr-2" />
        Back to Digest
      </Link>
    </main>
  );
}
