"use client";

import { useRouter } from "next/navigation";
import { Star } from "lucide-react";
import { cn } from "@/lib/utils";

interface FavoriteButtonProps {
  itemId: string;
  isFavorite: boolean;
  className?: string;
}

export function FavoriteButton({
  itemId,
  isFavorite,
  className,
}: FavoriteButtonProps) {
  const router = useRouter();

  const handleClick = async () => {
    const method = isFavorite ? "DELETE" : "POST";
    const url = isFavorite
      ? `/api/favorites?item_id=${encodeURIComponent(itemId)}`
      : "/api/favorites";
    const res = await fetch(url, {
      method,
      ...(method === "POST"
        ? {
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ item_id: itemId }),
          }
        : {}),
    });
    if (res.ok) {
      router.refresh();
    }
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm transition-colors",
        isFavorite
          ? "text-amber-500 hover:text-amber-600 bg-amber-50"
          : "text-gray-500 hover:text-amber-500 hover:bg-gray-100",
        className
      )}
      title={isFavorite ? "Remove from favorites" : "Add to favorites"}
    >
      <Star
        className="h-4 w-4"
        fill={isFavorite ? "currentColor" : "none"}
        stroke="currentColor"
      />
      {isFavorite ? "Saved" : "Save"}
    </button>
  );
}
